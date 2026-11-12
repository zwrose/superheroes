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
    ("ping @zwrose-no-such-login-0000000000000000000", ["@zwrose-no-such-login-0000000000000000000"]),
    ("@1000000000000000000000000000000000000000 at line start", ["@1000000000000000000000000000000000000000"]),
    ("collector @5740000000000000000000000000000000000000", ["@5740000000000000000000000000000000000000"]),
    ("(@octo-no-such-login-000000000000000000000)", ["@octo-no-such-login-000000000000000000000"]),
    ('"@octo-no-such-login-000000000000000000000"', ["@octo-no-such-login-000000000000000000000"]),
    ("*@octo-no-such-login-000000000000000000000*", ["@octo-no-such-login-000000000000000000000"]),
    ("\\@octo-no-such-login-000000000000000000000", ["@octo-no-such-login-000000000000000000000"]),
    ("@octo-no-such-login-000000000000000000000.", ["@octo-no-such-login-000000000000000000000"]),
    ("@octo-no-such-login-000000000000000000000. next", ["@octo-no-such-login-000000000000000000000"]),
    ("@org-no-such-login-0000000000000000000000/team", ["@org-no-such-login-0000000000000000000000"]),
    (TICK + "x" + TICK + "@8930000000000000000000000000000000000000", ["@8930000000000000000000000000000000000000"]),
    ("broken " + TICK + " example @8930000000000000000000000000000000000000", ["@8930000000000000000000000000000000000000"]),
    ("+@octo-no-such-login-000000000000000000000 hi", ["@octo-no-such-login-000000000000000000000"]),
]

HEALTHY = [
    TICK + "@octo-no-such-login-000000000000000000000" + TICK,
    TICK * 2 + "a " + TICK + " @octo-no-such-login-000000000000000000000" + TICK * 2,
    FENCE + "python\n@pytest.fixture\ndef f(): pass\n" + FENCE + "\n",
    "~~~\n@pytest.fixture\n~~~\n",
    FENCE + "\n@octo-no-such-login-000000000000000000000\n" + FENCE + "\n",
    "~~~\n@octo-no-such-login-000000000000000000000\n~~~\n",
    "a.b@example.com",
    "ops+@example.com",
    "<ops+@example.com>",
    "x@octo-no-such-login-000000000000000000000",
    "_@octo-no-such-login-000000000000000000000",
    "<slot>@<generation>",
    "answers/card@3",
    "@@ -1,2 +1,3 @@",
    "@<pointer>",
    "@-octo",
]

# the body every wiring test sends: a bare mention, and the healthy sibling that must pass untouched
BAD = "Result.\n\nping @zwrose-no-such-login-0000000000000000000\n"
GOOD = ("Result.\n\nping " + TICK + "@zwrose-no-such-login-0000000000000000000" + TICK + ", mail a.b@example.com\n\n" + FENCE + "python\n"
        "@pytest.fixture\ndef f(): pass\n" + FENCE + "\n")


def _tokens(text):
    return [m["mention"] for m in mg.bare_mentions(text)]


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
        text = "before\n" + fence + "\n@pytest.fixture\n@octo-no-such-login-000000000000000000000\n" + fence + "\nafter @octo-no-such-login-000000000000000000000\n"
        assert mg.bare_mentions(text) == [{"line": 6, "mention": "@octo-no-such-login-000000000000000000000"}]
        assert mg.check("x\n" + fence + "\n@pytest.fixture\n@octo-no-such-login-000000000000000000000\n" + fence + "\n") == {"ok": True}


def test_g3_an_inline_code_span_masks_its_mention_and_only_its_own():
    # axis: G3 — a mention inside an inline code span is not reported
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo_2453_mention_guard.md
    assert mg.check(TICK + "@octo-no-such-login-000000000000000000000" + TICK) == {"ok": True}
    assert mg.check(TICK * 2 + "a " + TICK + " @octo-no-such-login-000000000000000000000" + TICK * 2) == {"ok": True}
    assert _tokens(TICK + "@a-no-such-login-000000000000000000000000" + TICK + " and @b-no-such-login-000000000000000000000000") == ["@b-no-such-login-000000000000000000000000"]
    assert _tokens("\\" + TICK + "@a-no-such-login-000000000000000000000000" + TICK) == ["@a-no-such-login-000000000000000000000000"]  # a backslash escapes the opening backtick


def test_g4_an_email_shaped_at_sign_is_not_a_login():
    # axis: G4 — the email boundary: a login must end at a non-word character, not run into a dotted domain
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo_2453_mention_guard.md
    for text in ("ops+@example.com", "a.b@example.com", "<ops+@example.com>", "see ops+@example.com now"):
        assert mg.check(text) == {"ok": True}
    assert _tokens("hi @example.com") == []  # a login that runs into a dotted domain is an address, not a mention
    assert _tokens("hi @example-no-such-login-000000000000000000. ok") == ["@example-no-such-login-000000000000000000"]


def test_line_numbers_are_one_based_and_in_text_order():
    text = "a\n@one-no-such-login-0000000000000000000000\n" + FENCE + "\n@no-no-such-login-00000000000000000000000\n" + FENCE + "\nb @two-no-such-login-0000000000000000000000\n"
    assert mg.bare_mentions(text) == [{"line": 2, "mention": "@one-no-such-login-0000000000000000000000"}, {"line": 6, "mention": "@two-no-such-login-0000000000000000000000"}]


# ---------------------------------------------------------------- wrap


def test_g5_wrap_puts_a_mention_in_a_code_span():
    # axis: G5 — wrap's delimiter is one backtick longer than any run in the text
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo_2453_mention_guard.md
    wrapped = mg.wrap("ping @zwrose-no-such-login-0000000000000000000")
    assert wrapped == "ping " + TICK + "@zwrose-no-such-login-0000000000000000000" + TICK
    assert mg.bare_mentions(wrapped) == []


def test_g5_wrap_never_pairs_with_an_existing_backtick():
    # axis: G5 — the inserted delimiter cannot pair with an existing run
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo_2453_mention_guard.md
    text = "broken " + TICK + " example @8930000000000000000000000000000000000000"
    wrapped = mg.wrap(text)
    assert mg.bare_mentions(wrapped) == []
    assert wrapped == "broken " + TICK + " example " + TICK * 2 + "@8930000000000000000000000000000000000000" + TICK * 2
    assert wrapped.startswith("broken " + TICK + " ")  # the original backtick is still there, still unmatched
    assert mg.wrap(wrapped) == wrapped


@pytest.mark.parametrize("text", [
    "ping @zwrose-no-such-login-0000000000000000000", "broken " + TICK + " example @8930000000000000000000000000000000000000", "@a-no-such-login-000000000000000000000000 @b-no-such-login-000000000000000000000000", "\\@octo-no-such-login-000000000000000000000", TICK + "@a-no-such-login-000000000000000000000000", "@a-no-such-login-000000000000000000000000" + TICK,
    "x " + TICK * 3 + " @a-no-such-login-000000000000000000000000 @b-no-such-login-000000000000000000000000 " + TICK * 2 + " @c-no-such-login-000000000000000000000000", "line one @a-no-such-login-000000000000000000000000\r\nline two @b-no-such-login-000000000000000000000000\r\n", "(@a-no-such-login-000000000000000000000000)\n@b-no-such-login-000000000000000000000000.\n",
])
def test_wrap_is_idempotent_and_leaves_no_bare_mention(text):
    wrapped = mg.wrap(text)
    assert mg.bare_mentions(wrapped) == []
    assert mg.wrap(wrapped) == wrapped


def test_wrap_keeps_everything_but_the_wrapped_tokens():
    text = "keep " + TICK + "@kept-no-such-login-000000000000000000000" + TICK + " and ops+@example.com\n" + FENCE + "\n@pytest.fixture\n" + FENCE + "\n@x-no-such-login-000000000000000000000000\n"
    wrapped = mg.wrap(text)
    assert wrapped == text[:text.rindex("@")] + TICK * 4 + "@x-no-such-login-000000000000000000000000" + TICK * 4 + "\n"  # the fence's run of three makes the delimiter four


# ---------------------------------------------------------------- the edges


@pytest.mark.parametrize("value", [None, 5, b"@octo-no-such-login-000000000000000000000", ["@octo-no-such-login-000000000000000000000"], {"a": "@octo-no-such-login-000000000000000000000"}])
def test_e1_non_string_input_is_no_mention(value):
    # E1: bare_mentions returns [], check is ok, wrap returns the value as it came
    assert mg.bare_mentions(value) == []
    assert mg.check(value) == {"ok": True}
    assert mg.wrap(value) is value


def test_e2_empty_text_is_clean():
    assert mg.bare_mentions("") == [] and mg.check("") == {"ok": True} and mg.wrap("") == ""


def test_e3_a_column_0_unterminated_fence_masks_to_the_end():
    # E3: GFM renders a column-0 fence with no closer as code to the end of the document, so it masks every line
    # after its opener; the text before it is still scanned
    text = "top\n" + FENCE + "\n@octo-no-such-login-000000000000000000000\nmore @octo-no-such-login-000000000000000000000\n"
    assert mg.bare_mentions(text) == []
    assert mg.check(text) == {"ok": True}
    assert _tokens("@before-no-such-login-0000000000000000000\n" + text) == ["@before-no-such-login-0000000000000000000"]


def test_e3_a_closed_fence_with_an_indented_closer_masks_nothing():
    # E3: the opener is at column 0 but the closer is indented, which is what a list-contained fence looks like to
    # md_fence; the two readings disagree, so the lines between are scanned
    text = FENCE + "\n@octo-no-such-login-000000000000000000000\n  " + FENCE + "\nafter @hubot-no-such-login-00000000000000000000\n"
    assert _tokens(text) == ["@octo-no-such-login-000000000000000000000", "@hubot-no-such-login-00000000000000000000"]
    assert [m["line"] for m in mg.bare_mentions(text)] == [2, 4]


def test_a_fence_in_a_list_extended_cannot_pair_its_indented_closer_with_a_later_fence():
    # axis: G20 — md_fence pairs the indented closer (line 3) with the column-0 fence at line 7; that block's opener
    # is indented, so it masks nothing and the mention on line 5 is reported
    text = ("- " + FENCE + "\n  example\n  " + FENCE + "\n\nping @octo-no-such-login-000000000000000000000\n\n" + FENCE + "\nmore\n" + FENCE + "\n")
    assert mg.bare_mentions(text) == [{"line": 5, "mention": "@octo-no-such-login-000000000000000000000"}]
    assert mg.check(text)["reason"] == "bare-mention"


def test_a_fence_inside_a_list_cannot_mask_the_prose_after_it():
    # axis: the list-contained fence of the review's finding; the mention after it is reported and refused
    text = "- " + FENCE + "\n  example\n  " + FENCE + "\n\nping @octo-no-such-login-000000000000000000000\n"
    assert [m["line"] for m in mg.bare_mentions(text)] == [5]
    assert mg.check(text)["reason"] == "bare-mention"


def test_a_code_span_crossing_a_line_break_pairs_across_it():
    # axis: GFM pairs a code span across a paragraph's lines, so the closer on line two leaves the mention outside
    text = "begin " + TICK + "code\nend" + TICK + " then @octo-no-such-login-000000000000000000000 " + TICK + "literal\n"
    assert [m["line"] for m in mg.bare_mentions(text)] == [2]
    multi = TICK + "first\nsecond" + TICK + " @octo-no-such-login-000000000000000000000 " + TICK + "tail" + TICK + "\n"
    assert _tokens(multi) == ["@octo-no-such-login-000000000000000000000"]


def test_a_span_the_line_alone_does_not_pair_is_a_doubt_and_reports():
    # axis: G17 — code masks a mention only when its own line pairs it too, so a backtick pair that exists only
    # across the line break leaves the mention reported (a doubt reports)
    text = TICK + "a\n@octo-no-such-login-000000000000000000000 b" + TICK + "\n"
    assert mg.bare_mentions(text) == [{"line": 2, "mention": "@octo-no-such-login-000000000000000000000"}]
    assert mg.bare_mentions(mg.wrap(text)) == []


def test_a_paragraph_grouping_that_crosses_a_heading_does_not_pair_a_backtick_across_blocks():
    # axis: G18 — the paragraph reading pairs the first line's backtick with the second line's; the heading reading
    # does not, and the mention between the spans is a doubt that reports
    text = "# head " + TICK + "a\nmore" + TICK + " @octo-no-such-login-000000000000000000000 " + TICK + "b" + TICK + "\n"
    assert _tokens(text) == ["@octo-no-such-login-000000000000000000000"]


def test_a_paragraph_grouping_that_crosses_a_list_item_does_not_pair_a_backtick_across_items():
    # axis: G18 — the same across a list-item boundary
    text = "- " + TICK + "a\n- b" + TICK + " @octo-no-such-login-000000000000000000000 " + TICK + "c" + TICK + "\n"
    assert _tokens(text) == ["@octo-no-such-login-000000000000000000000"]


def test_a_table_row_without_a_leading_pipe_pairs_code_spans_cell_by_cell():
    # axis: G19 — a row with no leading pipe is still a row: a backtick in one cell cannot pair with one in another
    text = "a | b\n--- | ---\n" + TICK + " | @octo-no-such-login-000000000000000000000 " + TICK + "\n"
    assert [m["line"] for m in mg.bare_mentions(text)] == [3]
    assert mg.bare_mentions(mg.wrap(text)) == []
    inside = "a | b\n--- | ---\nx | " + TICK + "@octo-no-such-login-000000000000000000000" + TICK + "\n"
    assert mg.bare_mentions(inside) == []


def test_e4_an_escaped_pipe_is_no_cell_boundary():
    # E4: a line with only an escaped pipe has no cell reading, so a span across the escaped pipe still masks
    text = TICK + "a \\| @octo-no-such-login-000000000000000000000 b" + TICK + "\n"
    assert mg.bare_mentions(text) == []


def test_a_link_destination_masks_nothing_beyond_its_bare_url():
    # axis: no link-destination mask exists; only a hosted bare URL masks, so the at-sign after `(b)` is reported
    text = "[package](https://example.com/a(b)/@scope-no-such-login-00000000000000000000/pkg)\n"
    assert _tokens(text) == ["@scope-no-such-login-00000000000000000000"]
    # healthy sibling: a hosted bare URL still masks its at-sign
    assert mg.bare_mentions("[package](https://example.com/b/@scope-no-such-login-00000000000000000000/pkg)\n") == []


def test_e5_an_html_block_line_with_a_url_holding_an_at_sign_is_reported():
    # E5: on a raw HTML line no URL masks, so the URL's at-sign is reported as well as the bare mention
    text = "<p>see https://example.com/@scope-no-such-login-00000000000000000000/pkg and @octo-no-such-login-000000000000000000000</p>\n"
    assert _tokens(text) == ["@scope-no-such-login-00000000000000000000", "@octo-no-such-login-000000000000000000000"]
    # healthy sibling: a code element on a raw HTML line still masks
    assert mg.bare_mentions("<p><code>@octo-no-such-login-000000000000000000000</code></p>\n") == []


def test_table_cells_pair_code_spans_on_their_own():
    # axis: a backtick in one cell cannot pair with one in another cell
    table = "| a | b | c |\n| --- | --- | --- |\n| " + TICK + "x | @octo-no-such-login-000000000000000000000 | y" + TICK + " |\n"
    assert [m["line"] for m in mg.bare_mentions(table)] == [3]
    assert mg.wrap(table) == table.replace("@octo-no-such-login-000000000000000000000", TICK * 2 + "@octo-no-such-login-000000000000000000000" + TICK * 2)
    inside = "| a | b |\n| --- | --- |\n| x | " + TICK + "@octo-no-such-login-000000000000000000000" + TICK + " |\n"
    assert mg.bare_mentions(inside) == []


def test_an_at_sign_inside_a_link_or_url_is_left_alone():
    # axis: GitHub renders a link destination, an autolink and a bare URL as an anchor, which it never mentions in
    for text in ("[package](https://www.npmjs.com/package/@playwright-no-such-login-000000000000000/test)\n",
                 "see <https://www.npmjs.com/package/@playwright-no-such-login-000000000000000/test> now\n",
                 "see https://www.npmjs.com/package/@playwright-no-such-login-000000000000000/test now\n"):
        assert mg.bare_mentions(text) == []
        assert mg.wrap(text) == text
    # a URL inside a raw HTML block masks nothing, so its at-sign is reported
    assert _tokens("<div><a href=\"https://www.npmjs.com/package/@playwright-no-such-login-000000000000000/test\">pkg</a></div>\n") == ["@playwright-no-such-login-000000000000000"]
    # the link text is still prose, and a mention beside a URL is still reported
    assert _tokens("[ask @octo-no-such-login-000000000000000000000](https://example.com/x) and https://example.com/@ok-no-such-login-00000000000000000000000 then @hubot-no-such-login-00000000000000000000\n") == [
        "@octo-no-such-login-000000000000000000000", "@hubot-no-such-login-00000000000000000000"]


def test_a_raw_html_block_is_scanned_and_wrapped_in_a_code_element():
    # axis: a backtick inside a raw HTML block is literal, so it masks nothing and wrap uses a code element
    text = "<div>\n" + TICK + "@octo-no-such-login-000000000000000000000" + TICK + " and @hubot-no-such-login-00000000000000000000\n</div>\n\nafter " + TICK + "@kept-no-such-login-000000000000000000000" + TICK + "\n"
    assert _tokens(text) == ["@octo-no-such-login-000000000000000000000", "@hubot-no-such-login-00000000000000000000"]
    wrapped = mg.wrap(text)
    assert "<code>@hubot-no-such-login-00000000000000000000</code>" in wrapped and "<code>@octo-no-such-login-000000000000000000000</code>" in wrapped
    assert wrapped.endswith("after " + TICK + "@kept-no-such-login-000000000000000000000" + TICK + "\n")
    assert mg.bare_mentions(wrapped) == [] and mg.wrap(wrapped) == wrapped


def test_e4_a_mention_on_the_same_line_as_a_closed_span_but_outside_it_is_reported():
    assert _tokens(TICK + "@in-no-such-login-00000000000000000000000" + TICK + " then @out-no-such-login-0000000000000000000000") == ["@out-no-such-login-0000000000000000000000"]
    assert mg.wrap(TICK + "@in-no-such-login-00000000000000000000000" + TICK + " then @out-no-such-login-0000000000000000000000") == TICK + "@in-no-such-login-00000000000000000000000" + TICK + " then " + TICK * 2 + "@out-no-such-login-0000000000000000000000" + TICK * 2


def test_e5_crlf_line_endings_keep_fences_and_lines_working():
    fenced = "a\r\n" + FENCE + "\r\n@octo-no-such-login-000000000000000000000\r\n" + FENCE + "\r\n@bare-no-such-login-000000000000000000000\r\n"
    assert mg.bare_mentions(fenced) == [{"line": 5, "mention": "@bare-no-such-login-000000000000000000000"}]
    assert mg.bare_mentions("x\r\n@octo-no-such-login-000000000000000000000\r\n") == [{"line": 2, "mention": "@octo-no-such-login-000000000000000000000"}]
    assert mg.wrap("x\r\n@octo-no-such-login-000000000000000000000\r\n") == "x\r\n" + TICK + "@octo-no-such-login-000000000000000000000" + TICK + "\r\n"


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
                                      "mentions": [{"line": 3, "mention": "@zwrose-no-such-login-0000000000000000000"}]}


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
    out = _cli("wrap", stdin="ping @zwrose-no-such-login-0000000000000000000\n")
    assert (out.returncode, out.stdout) == (0, "ping " + TICK + "@zwrose-no-such-login-0000000000000000000" + TICK + "\n")


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


def _assert_refusal(result, mention="@zwrose-no-such-login-0000000000000000000"):
    assert result["ok"] is False and result["reason"] == "bare-mention"
    assert [m["mention"] for m in result["mentions"]] == [mention]
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


@pytest.mark.parametrize("body", [
    # a span that closes on line two leaves the mention outside it; the trailing backtick opens nothing
    "begin " + TICK + "code\nend" + TICK + " then @octo-no-such-login-000000000000000000000 " + TICK + "literal\n",
    # a table row's cells pair on their own, so the backticks in two cells never make a span around the mention
    "| a | b |\n| --- | --- |\n| " + TICK + " | @octo-no-such-login-000000000000000000000 " + TICK + " |\n",
], ids=["multi-line-span", "leading-pipe-table"])
def test_g6_post_comment_refuses_a_mention_a_single_reading_would_have_masked(tmp_path, body):
    # axis: G18, G19 — a mention one reading masks and another does not is a doubt: the writer refuses before any gh call
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo_2453_mention_guard.md
    run = _Gh()
    result = cb.post_comment("o/r", 1, _body_file(tmp_path, body), run=run, env={})
    _assert_refusal(result, mention="@octo-no-such-login-000000000000000000000")
    assert result["url"] is None and run.calls == []


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
    _assert_refusal(cb.note_text("ping @zwrose-no-such-login-0000000000000000000"))
    code, out = _main(capsys, "note", "--question-file", _body_file(tmp_path, "ping @zwrose-no-such-login-0000000000000000000"))
    assert code == 1 and out["reason"] == "bare-mention"
    healthy = cb.note_text(GOOD)
    assert healthy["comment"].startswith(cb.NOTE_HEADER) and GOOD.strip() in healthy["comment"]
    code, out = _main(capsys, "note", "--question-file", _body_file(tmp_path, GOOD))
    assert code == 0 and "comment" in out


def test_g9_progress_text_refuses_a_bare_mention_and_the_cli_exits_1(capsys):
    # axis: G9 — the composed progress comment is checked before it is returned
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo_2453_mention_guard.md
    started = "2026-01-02T03:04:05Z"
    _assert_refusal(cb.progress_text("building", "ping @zwrose-no-such-login-0000000000000000000", started, 30))
    code, out = _main(capsys, "progress", "--phase", "building", "--running", "ping @zwrose-no-such-login-0000000000000000000",
                      "--started", started, "--expected-minutes", "30")
    assert code == 1 and out["reason"] == "bare-mention"
    healthy = cb.progress_text("building", "ping " + TICK + "@zwrose-no-such-login-0000000000000000000" + TICK + " a.b@example.com", started, 30)
    assert healthy["ok"] is True and "a.b@example.com" in healthy["comment"]


def test_g10_terminal_text_refuses_a_bare_mention_and_the_cli_exits_1(tmp_path, capsys):
    # axis: G10 — the composed handback, stop or park is checked before it is returned
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo_2453_mention_guard.md
    for kind in ("handback", "stop", "park"):
        _assert_refusal(cb.terminal_text(kind, "ping @zwrose-no-such-login-0000000000000000000"))
    code, out = _main(capsys, "terminal", "--kind", "stop", "--text-file", _body_file(tmp_path, "ping @zwrose-no-such-login-0000000000000000000"))
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
    bad = TPB.FIXED + "ping @zwrose-no-such-login-0000000000000000000\n"
    sd = TPB._staged_fixed(tmp_path, fixed=bad)
    gh = TPB.FakeGh(views=[TPB.BODY, bad])
    out = PBS.publish(sd, 7, runner=gh)
    assert PBS.REASON_BARE_MENTION == "bare-mention"
    assert (out["ok"], out["outcome"], out["reason"]) == (False, "refused", "bare-mention")
    assert out["mentions"] == [{"line": bad.count("\n"), "mention": "@zwrose-no-such-login-0000000000000000000"}]
    assert gh.edits() == []
    assert TPB._read(PBS.paths(sd)["staged"]) == bad
    assert TPB._receipt(sd) == out
    assert "login" in PBS.record_line(sd)
    # axis: the refusal carries the guard's remedy so the reader learns how to fix the body
    assert out["remedy"] == mg.REMEDY


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
    result = _write(TVS.SLOT + "ping @zwrose-no-such-login-0000000000000000000\n")
    assert result["ok"] is False and result["reason"] == "write-failed"
    assert result["detail"].startswith("bare-mention:")
    assert "@zwrose-no-such-login-0000000000000000000" in result["detail"] and "code span" in result["detail"]
    assert "newBody" not in result
    with pytest.raises(vs._Refusal) as raised:
        vs.check_slot_text("ping @zwrose-no-such-login-0000000000000000000")
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
    assert TICK + "@zwrose-no-such-login-0000000000000000000" + TICK in sent
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
    rec = _record_with("ping @zwrose-no-such-login-0000000000000000000")
    body = rr.render(rec)
    assert mg.bare_mentions(body) == []
    prose = body.split("<details>")[0]
    assert TICK + "@zwrose-no-such-login-0000000000000000000" + TICK in prose and "ping @zwrose-no-such-login-0000000000000000000" not in prose
    assert rr._json_block(body)["lane"]["reason"] == "ping @zwrose-no-such-login-0000000000000000000"


def test_g15_the_head_comment_summary_of_a_record_in_parts_is_wrapped_too():
    rec = _record_with("ping @zwrose-no-such-login-0000000000000000000")
    rec["whatIsMissing"] = rec["whatIsMissing"] + ["w" * rr.MAX_BODY_CHARS]
    plan = rr.render_plan(rec)
    assert plan.parts
    head = plan.head(list(range(1, len(plan.parts) + 1)))
    assert mg.bare_mentions(head) == []
    assert TICK + "@zwrose-no-such-login-0000000000000000000" + TICK in head.split("<details>")[0]


def test_g15_a_healthy_record_summary_is_unchanged():
    healthy = _record_with("big change, see " + TICK + "@zwrose-no-such-login-0000000000000000000" + TICK + " and a.b@example.com")
    body = rr.render(healthy)
    assert "big change, see " + TICK + "@zwrose-no-such-login-0000000000000000000" + TICK + " and a.b@example.com" in body.split("<details>")[0]


@pytest.mark.parametrize("text,line", [
    ("<div>\n~~~\n@octo-no-such-login-000000000000000000000\n~~~\n</div>\n", 3),
    ("<div>\n~~~\n</div>\n\nping @octo-no-such-login-000000000000000000000\n", 5),
    ("<div>\n~~~\n@octo-no-such-login-000000000000000000000\n</div>\n", 3),
], ids=["closed-fence-in-html", "unterminated-fence-in-html-then-prose", "unterminated-fence-in-html"])
def test_a_fence_shaped_line_inside_raw_html_masks_nothing(text, line):
    # axis: inside a raw HTML block a fence-shaped line is literal text, so the mention stays reported and refused
    assert [m["line"] for m in mg.bare_mentions(text)] == [line]
    assert mg.check(text)["reason"] == "bare-mention"
    assert mg.bare_mentions(mg.wrap(text)) == []


def test_a_tag_inside_a_fence_starts_no_html_block():
    # axis: a fenced HTML example is code, so the escaped code-shaped prose after the fence is still scanned
    text = "~~~\n<div>\n~~~\n\\<code>@octo-no-such-login-000000000000000000000\\</code>\n"
    assert [m["line"] for m in mg.bare_mentions(text)] == [4]
    assert mg.check(text)["reason"] == "bare-mention"
    assert mg.bare_mentions(mg.wrap(text)) == []
    # inside a real HTML block an escaped code tag masks nothing either
    assert [m["line"] for m in mg.bare_mentions("<div>\n\\<code>@octo-no-such-login-000000000000000000000\\</code>\n</div>\n")] == [2]


@pytest.mark.parametrize("text,line", [
    ("<div>\n~~~\n</div>\n\n<div>\n" + TICK + "@octo-no-such-login-000000000000000000000" + TICK + "\n</div>\n", 6),
    ("  ~~~\n\n<div>\n" + TICK + "@octo-no-such-login-000000000000000000000" + TICK + "\n</div>\n", 4),
    ("<p>\n" + FENCE + "\n</p>\n\n<p>\n" + TICK + "@octo-no-such-login-000000000000000000000" + TICK + "\n</p>\n", 6),
], ids=["html-fence-then-html", "indented-fence-then-html", "html-backtick-fence-then-html"])
def test_html_and_fence_context_are_read_in_one_pass(text, line):
    # axis: a fence-shaped line inside raw HTML, or an indented one, opens no fence, so a later HTML block is
    # still read as HTML and its backticks mask nothing
    assert [m["line"] for m in mg.bare_mentions(text)] == [line]
    assert mg.check(text)["reason"] == "bare-mention"
    assert mg.bare_mentions(mg.wrap(text)) == []


@pytest.mark.parametrize("text,line", [
    ("  " + FENCE + "\nexample\n" + FENCE + "\n@octo-no-such-login-000000000000000000000\n", 4),
    ("  ~~~\n~~~\nping @octo-no-such-login-000000000000000000000\n", 3),
    ("- " + FENCE + "\n  x\n  " + FENCE + "\n" + FENCE + "\n@octo-no-such-login-000000000000000000000\n", 5),
], ids=["indented-opener-column-0-closer", "indented-tilde-then-closer", "list-fence-then-column-0-fence-shape"])
def test_an_indented_fence_consumes_its_closer_so_it_opens_no_masking_fence(text, line):
    # axis: an indented opener masks nothing and takes its closer with it, so that closer opens no fence
    assert line in [m["line"] for m in mg.bare_mentions(text)]
    assert mg.check(text)["reason"] == "bare-mention"


def test_a_real_column_0_fence_still_masks():
    # healthy sibling: a fenced block at column 0 still masks its content
    assert mg.bare_mentions(FENCE + "\n@octo-no-such-login-000000000000000000000\n" + FENCE + "\nplain\n") == []


@pytest.mark.parametrize("text", [
    "see ](@octo-no-such-login-000000000000000000000\n",
    "[x](@octo-no-such-login-000000000000000000000\n",
    "text ](@octo-no-such-login-000000000000000000000)\n",
    "[x] (@octo-no-such-login-000000000000000000000)\n",
], ids=["no-label-no-close", "no-close", "no-label", "space-before-paren"])
def test_an_incomplete_link_shape_masks_nothing(text):
    # axis: only a complete [label](destination) masks its destination; an incomplete shape masks nothing
    assert _tokens(text) == ["@octo-no-such-login-000000000000000000000"]


def test_a_link_destination_without_a_hosted_url_is_reported():
    # axis: a destination is not masked as a destination, so a relative one is reported, as is an escaped link
    assert _tokens("[pkg](/package/@scope-no-such-login-00000000000000000000/x)\n") == ["@scope-no-such-login-00000000000000000000"]
    assert _tokens("\\[x](@octo-no-such-login-000000000000000000000)\n") == ["@octo-no-such-login-000000000000000000000"]
    assert _tokens("[ask @octo-no-such-login-000000000000000000000](/x)\n") == ["@octo-no-such-login-000000000000000000000"]
    # healthy sibling: a hosted URL as the destination still masks
    assert mg.bare_mentions("[package](https://www.npmjs.com/package/@playwright-no-such-login-000000000000000/test)\n") == []


@pytest.mark.parametrize("text,line", [
    ("<pre>\n\n~~~\n</pre>\n@octo-no-such-login-000000000000000000000\n", 5),
    ("<pre>\n\n" + TICK + "@octo-no-such-login-000000000000000000000" + TICK + "\n</pre>\n", 3),
    ("<textarea>\n\n~~~\n</textarea>\n\nping @octo-no-such-login-000000000000000000000\n", 6),
], ids=["pre-blank-tilde-then-prose", "pre-blank-backticks", "textarea-blank-tilde-then-prose"])
def test_a_raw_text_html_block_runs_to_its_closing_tag(text, line):
    # axis: a blank line does not end a pre/script/style/textarea block, so a fence shape there opens no fence
    assert [m["line"] for m in mg.bare_mentions(text)] == [line]
    assert mg.check(text)["reason"] == "bare-mention"


def test_a_raw_text_block_closed_on_its_own_line_still_ends():
    # healthy sibling: once the closing tag is seen, a real fence after it still masks
    assert mg.bare_mentions("<pre>x</pre>\n\n" + FENCE + "\n@octo-no-such-login-000000000000000000000\n" + FENCE + "\n") == []


def test_any_type_1_closing_tag_ends_a_raw_text_block():
    # axis: a different kind-1 closing tag ends the block, so the later HTML block keeps the fence shape literal
    text = "<pre>\n</style>\n</pre>\n~~~\nping @octo-no-such-login-000000000000000000000\n"
    assert [m["line"] for m in mg.bare_mentions(text)] == [5]
    assert mg.check(text)["reason"] == "bare-mention"


def test_a_non_ascii_look_alike_closes_no_raw_text_block():
    # axis: tag case-folding is ASCII only, so a long-s look-alike closing tag leaves the pre block open
    text = "<pre>\n</" + "ſ" + "tyle>\n~~~\n</pre>\nping @octo-no-such-login-000000000000000000000\n"
    assert [m["line"] for m in mg.bare_mentions(text)] == [5]
    # healthy sibling: an ASCII closing tag in any case still closes it
    assert [m["line"] for m in mg.bare_mentions("<pre>\n</STYLE>\n</pre>\n~~~\nping @octo-no-such-login-000000000000000000000\n")] == [5]


@pytest.mark.parametrize("text", [
    "https://" + " " + "@octo-no-such-login-000000000000000000000\n",
    "éhttps://example.com/@octo-no-such-login-000000000000000000000\n",
    "http" + "ſ" + "://example.com/@octo-no-such-login-000000000000000000000\n",
], ids=["nbsp-after-scheme-over-reports", "accented-letter-before-scheme-over-reports", "long-s-scheme"])
def test_a_url_shape_the_mask_does_not_recognise_with_certainty_reports(text):
    # axis: the URL mask keeps Unicode space and word boundaries (stopping earlier than GitHub's autolinker, which
    # over-reports) and matches no look-alike scheme
    assert _tokens(text) == ["@octo-no-such-login-000000000000000000000"]


@pytest.mark.parametrize("text", [
    "see http://@octo-no-such-login-000000000000000000000 now\n",
    "see https:///@octo-no-such-login-000000000000000000000 now\n",
    "see <foo:@octo-no-such-login-000000000000000000000> now\n",
], ids=["hostless-url", "empty-host-url", "angle-shape-unlinked-scheme"])
def test_a_url_with_no_host_or_an_angle_shape_masks_nothing(text):
    # axis: the bare-URL mask needs an ASCII letter or digit right after `://`, and no angle shape masks
    assert _tokens(text) == ["@octo-no-such-login-000000000000000000000"]


def test_a_real_bare_url_still_masks_in_any_scheme_case():
    # healthy sibling
    assert mg.bare_mentions("see HTTPS://example.com/@ok-no-such-login-00000000000000000000000 and https://example.com/@ok-no-such-login-00000000000000000000000\n") == []


@pytest.mark.parametrize("text", [
    "see https://bad_host/@octo-no-such-login-000000000000000000000 now\n",
    "see https://a.b_c/@octo-no-such-login-000000000000000000000 now\n",
], ids=["underscore-host", "underscore-in-last-segment"])
def test_a_url_whose_host_github_leaves_as_text_masks_nothing(text):
    # axis: the URL mask takes a host of ASCII letters, digits, dots and hyphens only
    assert _tokens(text) == ["@octo-no-such-login-000000000000000000000"]


def test_a_url_with_a_clean_host_and_a_port_or_query_still_masks():
    # healthy sibling
    assert mg.bare_mentions("see https://example.com:8080/@ok-no-such-login-00000000000000000000000 and https://example.com?u=@ok-no-such-login-00000000000000000000000 now\n") == []


@pytest.mark.parametrize("text, line", [
    ("<!--\n~~~\n-->\n\nping @octo-no-such-login-000000000000000000000\n", 5),
    ("<!--\n~~~\n-->\n@octo-no-such-login-000000000000000000000\n", 4),
    ("<?x\n```\n?>\n@octo-no-such-login-000000000000000000000\n", 4),
    ("<!X\n```\n>\n@octo-no-such-login-000000000000000000000\n", 4),
], ids=["comment-then-blank", "comment", "processing-instruction", "declaration"])
def test_a_fence_shaped_line_after_a_comment_or_declaration_opener_masks_nothing(text, line, tmp_path):
    # axis: after a comment, processing-instruction or declaration block opens, no column-0 fence masks
    assert [m["line"] for m in mg.bare_mentions(text)] == [line]
    run = _Gh()
    result = cb.post_comment("o/r", 1, _body_file(tmp_path, text), run=run, env={})
    assert result["ok"] is False and result["reason"] == "bare-mention" and run.calls == []


def test_a_fence_with_no_comment_before_it_still_masks():
    # healthy sibling: a comment after a closed fence leaves that fence masking
    assert mg.bare_mentions("```\n@ok-no-such-login-00000000000000000000000\n```\n<!-- note -->\n") == []


@pytest.mark.parametrize("text", [
    'see <span title="`">@octo-no-such-login-000000000000000000000</span> `\n',
    'see <a href="x">link</a> and `@octo-no-such-login-000000000000000000000`\n',
], ids=["backtick-in-attribute", "span-after-a-tag"])
def test_a_code_span_after_a_tag_start_masks_nothing(text):
    # axis: a backtick after a tag start may sit inside an attribute, so that span and every later one mask nothing
    assert _tokens(text) == ["@octo-no-such-login-000000000000000000000"]


def test_a_code_span_before_any_tag_still_masks():
    # healthy sibling: a span holding a tag does not stop a later span from masking
    assert mg.bare_mentions("`<div>` and `@ok-no-such-login-00000000000000000000000` then <b>x</b>\n") == []


@pytest.mark.parametrize("text", [
    '<div title="<code>">@octo-no-such-login-000000000000000000000</div></code>\n',
    '<div title="<code>">@octo-no-such-login-000000000000000000000<span title="</code>"></span></div>\n',
], ids=["opener-in-attribute", "both-tags-in-attributes"])
def test_a_code_element_holding_a_quote_masks_nothing(text):
    # axis: a code element holding a quote may start or end inside an attribute value, so it masks nothing
    assert _tokens(text) == ["@octo-no-such-login-000000000000000000000"]


def test_a_code_element_with_no_quote_still_masks():
    # healthy sibling
    assert mg.bare_mentions("<div><code>@ok-no-such-login-00000000000000000000000</code></div>\n") == []


def test_a_comment_that_ends_on_its_own_line_leaves_later_fences_masking():
    # healthy sibling: a one-line marker comment (as the review record opens with) leaves its fences masking
    assert mg.bare_mentions("<!-- marker -->\n```\n@ok-no-such-login-00000000000000000000000\n```\n<?x ?>\n~~~\n@ok-no-such-login-00000000000000000000000\n~~~\n") == []


def test_wrap_leaves_punctuation_after_a_mention_outside_the_span():
    # healthy sibling: only an attached at-sign joins the span
    assert mg.wrap("ping @octo-no-such-login-000000000000000000000, then @hubot-no-such-login-00000000000000000000.\n") == "ping `@octo-no-such-login-000000000000000000000`, then `@hubot-no-such-login-00000000000000000000`.\n"


@pytest.mark.parametrize("text", [
    "see ftp://example.com/@octo-no-such-login-000000000000000000000 now\n",
    TICK + "https://example.com/" + TICK + "@octo-no-such-login-000000000000000000000\n",
    "| https://example.com/|@octo-no-such-login-000000000000000000000 |\n",
    "[link https://example.com/]@octo-no-such-login-000000000000000000000\n",
], ids=["ftp-scheme", "code-span-ends-in-address", "address-runs-into-next-cell", "bracketed-address"])
def test_an_address_github_does_not_link_whole_masks_nothing(text):
    # axis: only an http(s) URL masks, and a path running into a backtick, pipe or bracket masks nothing
    assert _tokens(text) == ["@octo-no-such-login-000000000000000000000"]


def test_an_http_url_with_a_plain_path_still_masks():
    # healthy sibling
    assert mg.bare_mentions("see https://example.com/a/@ok-no-such-login-00000000000000000000000?x=1#y now\n") == []


def test_a_doubled_backslash_before_a_tag_still_stops_later_code_spans():
    # axis: an escaped-looking tag start is a real tag after a doubled backslash, so later spans mask nothing
    assert _tokens("\\\\<span title=\"" + TICK + "\">@octo-no-such-login-000000000000000000000</span> " + TICK + "\n") == ["@octo-no-such-login-000000000000000000000"]


@pytest.mark.parametrize("text", [
    "<div><!-- <code>@octo-no-such-login-000000000000000000000</code> -->\n",
    "<div><![CDATA[<code>@octo-no-such-login-000000000000000000000</code>]]>\n",
], ids=["comment", "cdata"])
def test_a_code_element_on_an_html_line_holding_a_comment_opener_masks_nothing(text):
    # axis: on an HTML line holding `<!`, a code element may sit inside a comment or CDATA, so it masks nothing
    assert _tokens(text) == ["@octo-no-such-login-000000000000000000000"]


@pytest.mark.parametrize("text", ["ping &#64;octo-no-such-login-000000000000000000000 now\n", "ping &#x40;octo-no-such-login-000000000000000000000 now\n", "ping &commat;octo-no-such-login-000000000000000000000 now\n"],
                         ids=["decimal", "hex", "named"])
def test_an_at_sign_written_as_a_character_code_is_reported(text):
    # axis: GitHub decodes a character-code at-sign before its mention filter, so it is reported and wrapped
    assert _tokens(text) == ["@octo-no-such-login-000000000000000000000"]
    assert mg.bare_mentions(mg.wrap(text)) == []


def test_a_character_code_after_a_word_character_is_no_mention():
    # healthy sibling
    assert mg.bare_mentions("mail x&#64;ok-no-such-login-00000000000000000000000 and &amp;ok\n") == []


def test_a_no_break_space_line_does_not_end_an_html_block():
    # axis: a GFM blank line holds only ASCII spaces and tabs, so a no-break space keeps the HTML block open
    text = "<div>\n" + chr(160) + "\n~~~\n@alice-no-such-login-000000000000000000\n~~~\n</div>\n"
    assert _tokens(text) == ["@alice-no-such-login-000000000000000000"]


def test_a_space_only_line_still_ends_an_html_block():
    # healthy sibling: after a real blank line the fence masks again
    assert mg.bare_mentions("<div>\n \t\n~~~\n@ok-no-such-login-000000000000000000000\n~~~\n") == []


def test_a_block_starting_inside_a_run_cannot_pair_backticks_across_it():
    # axis: a reading starts from each line of the run, so a heading's backtick cannot pair across the next block
    text = "# h " + TICK + "a\np " + TICK + "b\nc " + TICK + "@alice-no-such-login-000000000000000000" + TICK + " d " + TICK + "\n"
    assert _tokens(text) == ["@alice-no-such-login-000000000000000000"]


def test_code_spans_on_consecutive_lines_and_list_items_still_mask():
    # healthy sibling
    text = "use " + TICK + "@ok-no-such-login-000000000000000000000" + TICK + " here\n- item " + TICK + "x" + TICK + "\n"
    assert mg.bare_mentions(text) == []
    assert mg.bare_mentions(mg.wrap("# h " + TICK + "a\np @ok-no-such-login-000000000000000000000\n")) == []


@pytest.mark.parametrize("text", [
    "say " + TICK + "@alice-no-such-login-000000000000000000\n# h " + TICK + "\n",
    "# heading " + TICK + "@alice-no-such-login-000000000000000000\nnext " + TICK + "\n",
], ids=["heading-after", "heading-before"])
def test_a_span_must_close_on_the_mentions_own_line(text):
    # axis: the line's own reading is required, so a later block cannot close a mention's span
    assert _tokens(text) == ["@alice-no-such-login-000000000000000000"]


def test_a_long_run_with_no_mention_takes_no_suffix_readings(monkeypatch):
    # axis: a run with no mention is not parsed suffix by suffix
    calls = []
    real = mg._code_spans
    monkeypatch.setattr(mg, "_code_spans", lambda line: calls.append(1) or real(line))
    assert mg.bare_mentions("".join("line " + TICK + "x" + TICK + " %d\n" % i for i in range(200))) == []
    assert calls == []
    assert mg.bare_mentions("a " + TICK + "@ok-no-such-login-000000000000000000000" + TICK + "\nb\n") == []
