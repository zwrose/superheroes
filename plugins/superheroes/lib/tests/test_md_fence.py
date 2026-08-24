"""Tests for md_fence — CommonMark §4.5 fence line classifier."""
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import md_fence as mf

T = mf.KIND_TEXT
O = mf.KIND_OPENER
C = mf.KIND_CONTENT
X = mf.KIND_CLOSER

CORPUS = [
    pytest.param(
        "closer_carrying_trailing_text",
        [
            "```",
            "> quote",
            "```still-code",
            "more",
            "```",
        ],
        (O, C, C, C, X),
        None,
        id="closer_carrying_trailing_text",
    ),
    pytest.param(
        "longer_closer_closes",
        [
            "```",
            "inside",
            "`````",
        ],
        (O, C, X),
        None,
        id="longer_closer_closes",
    ),
    pytest.param(
        "shorter_run_does_not_close",
        [
            "`````",
            "```",
            "`````",
        ],
        (O, C, X),
        None,
        id="shorter_run_does_not_close",
    ),
    pytest.param(
        "backtick_not_closed_by_tildes",
        [
            "```",
            "~~~",
            "```",
        ],
        (O, C, X),
        None,
        id="backtick_not_closed_by_tildes",
    ),
    pytest.param(
        "tilde_not_closed_by_backticks",
        [
            "~~~",
            "```",
            "~~~",
        ],
        (O, C, X),
        None,
        id="tilde_not_closed_by_backticks",
    ),
    pytest.param(
        "indent_0_opens",
        ["```", "```"],
        (O, X),
        None,
        id="indent_0_opens",
    ),
    pytest.param(
        "indent_1_opens",
        [" ```", " ```"],
        (O, X),
        None,
        id="indent_1_opens",
    ),
    pytest.param(
        "indent_2_opens",
        ["  ```", "  ```"],
        (O, X),
        None,
        id="indent_2_opens",
    ),
    pytest.param(
        "indent_3_opens",
        ["   ```", "   ```"],
        (O, X),
        None,
        id="indent_3_opens",
    ),
    pytest.param(
        "indent_4_outside_is_text",
        ["    ```"],
        (T,),
        None,
        id="indent_4_outside_is_text",
    ),
    pytest.param(
        "indent_4_inside_is_content",
        [
            "```",
            "    ```",
            "```",
        ],
        (O, C, X),
        None,
        id="indent_4_inside_is_content",
    ),
    pytest.param(
        "tab_indent_not_fence",
        ["\t```"],
        (T,),
        None,
        id="tab_indent_not_fence",
    ),
    pytest.param(
        "backtick_in_info_not_opener",
        ["```a`b"],
        (T,),
        None,
        id="backtick_in_info_not_opener",
    ),
    pytest.param(
        "tilde_info_with_backtick_is_opener",
        ["~~~a`b", "~~~"],
        (O, X),
        None,
        id="tilde_info_with_backtick_is_opener",
    ),
    pytest.param(
        "nested_marker_inside_fence_is_content",
        [
            "```",
            "```py",
            "code here",
            "```",
        ],
        (O, C, C, X),
        None,
        id="nested_marker_inside_fence_is_content",
    ),
    pytest.param(
        "unterminated_fence",
        [
            "```",
            "line one",
            "line two",
        ],
        (O, C, C),
        1,
        id="unterminated_fence",
    ),
    pytest.param(
        "unterminated_fence_not_on_line_1",
        [
            "preamble",
            "```",
            "inside",
        ],
        (T, O, C),
        2,
        id="unterminated_fence_not_on_line_1",
    ),
    pytest.param(
        "closer_with_trailing_spaces",
        [
            "```",
            "inside",
            "```   ",
        ],
        (O, C, X),
        None,
        id="closer_with_trailing_spaces",
    ),
    pytest.param(
        "closer_with_trailing_tab",
        [
            "```",
            "inside",
            "```\t",
        ],
        (O, C, X),
        None,
        id="closer_with_trailing_tab",
    ),
    pytest.param(
        "tilde_closer_with_trailing_spaces",
        [
            "~~~",
            "inside",
            "~~~   ",
        ],
        (O, C, X),
        None,
        id="tilde_closer_with_trailing_spaces",
    ),
    pytest.param(
        "single_backtick_inline_code",
        ["`inline code without a closing backtick"],
        (T,),
        None,
        id="single_backtick_inline_code",
    ),
    pytest.param(
        "double_backtick_inline",
        ["``inline code without a closing run"],
        (T,),
        None,
        id="double_backtick_inline",
    ),
    pytest.param(
        "double_tilde_strikethrough",
        ["~~deleted~~"],
        (T,),
        None,
        id="double_tilde_strikethrough",
    ),
    pytest.param(
        "blank_and_whitespace_lines",
        [
            "",
            "   ",
            "\t",
            "plain text",
        ],
        (T, T, T, T),
        None,
        id="blank_and_whitespace_lines",
    ),
    pytest.param(
        "blank_lines_inside_fence",
        [
            "```",
            "line one",
            "",
            "   ",
            "line two",
            "```",
        ],
        (O, C, C, C, C, X),
        None,
        id="blank_lines_inside_fence",
    ),
    pytest.param(
        "closer_indent_differs_from_opener",
        [
            "```",
            "inside",
            "  ```",
        ],
        (O, C, X),
        None,
        id="closer_indent_differs_from_opener",
    ),
    pytest.param(
        "crlf_input",
        [
            "```\r",
            "> quote\r",
            "```still-code\r",
            "more\r",
            "```\r",
        ],
        (O, C, C, C, X),
        None,
        id="crlf_input",
    ),
    pytest.param(
        "empty_input",
        [],
        (),
        None,
        id="empty_input",
    ),
    pytest.param(
        "blockquote_container_fence_is_text",
        ["> ```py"],
        (T,),
        None,
        id="blockquote_container_fence_is_text",
    ),
]


@pytest.mark.parametrize(
    "_name, lines, expected_kinds, expected_unterminated",
    CORPUS,
)
def test_corpus(_name, lines, expected_kinds, expected_unterminated):
    result = mf.scan(lines)
    assert result.kinds == expected_kinds
    assert result.unterminated_opener_line == expected_unterminated


@pytest.mark.parametrize(
    "_name, lines, expected_kinds, expected_unterminated",
    CORPUS,
)
def test_corpus_invariant(_name, lines, expected_kinds, expected_unterminated):
    result = mf.scan(lines)
    assert len(result.kinds) == len(lines)
    for kind in result.kinds:
        assert kind in mf.KINDS
    for i, kind in enumerate(result.kinds):
        assert result.inert[i] == (kind != mf.KIND_TEXT)


def test_scan_rejects_non_str_line():
    with pytest.raises(TypeError, match="each line must be a str"):
        mf.scan([123])


def test_scan_non_str_error_names_offending_type():
    with pytest.raises(TypeError, match="got int"):
        mf.scan([123])


CONTEXT_CENSUS = [
    pytest.param(
        ["hello", "world"],
        (mf.TEXT, mf.TEXT),
        None,
        None,
        id="plain_text",
    ),
    pytest.param(
        ["```", "code", "```"],
        (mf.FENCE_OPENER, mf.FENCE_CONTENT, mf.FENCE_CLOSER),
        None,
        None,
        id="backtick_fence",
    ),
    pytest.param(
        ["~~~", "code", "~~~"],
        (mf.FENCE_OPENER, mf.FENCE_CONTENT, mf.FENCE_CLOSER),
        None,
        None,
        id="tilde_fence",
    ),
    pytest.param(
        ["```", "line one", "line two"],
        (mf.FENCE_OPENER, mf.FENCE_CONTENT, mf.FENCE_CONTENT),
        1,
        None,
        id="unterminated_fence",
    ),
    pytest.param(
        ["<pre>", "literal", "</pre>"],
        (mf.HTML_OPEN, mf.HTML_CONTENT, mf.HTML_CLOSE),
        None,
        None,
        id="pre_block",
    ),
    pytest.param(
        ["<script>", "js();", "</script>"],
        (mf.HTML_OPEN, mf.HTML_CONTENT, mf.HTML_CLOSE),
        None,
        None,
        id="script_block",
    ),
    pytest.param(
        ["<style>", "body {}", "</style>"],
        (mf.HTML_OPEN, mf.HTML_CONTENT, mf.HTML_CLOSE),
        None,
        None,
        id="style_block",
    ),
    pytest.param(
        ["<textarea>", "text", "</textarea>"],
        (mf.HTML_OPEN, mf.HTML_CONTENT, mf.HTML_CLOSE),
        None,
        None,
        id="textarea_block",
    ),
    pytest.param(
        ["<pre>x</pre>"],
        (mf.HTML_OPEN,),
        None,
        None,
        id="pre_single_line",
    ),
    pytest.param(
        ["<pre>", "still literal"],
        (mf.HTML_OPEN, mf.HTML_CONTENT),
        None,
        1,
        id="pre_unterminated",
    ),
    pytest.param(
        ["```", "<pre>", "not html", "```"],
        (mf.FENCE_OPENER, mf.FENCE_CONTENT, mf.FENCE_CONTENT, mf.FENCE_CLOSER),
        None,
        None,
        id="pre_inside_fence",
    ),
    pytest.param(
        ["<pre>", "```", "not a fence", "</pre>"],
        (mf.HTML_OPEN, mf.HTML_CONTENT, mf.HTML_CONTENT, mf.HTML_CLOSE),
        None,
        None,
        id="fence_inside_pre",
    ),
    pytest.param(
        ["<pre>", "x", "</PRE>"],
        (mf.HTML_OPEN, mf.HTML_CONTENT, mf.HTML_CLOSE),
        None,
        None,
        id="pre_close_mixed_case",
    ),
    pytest.param(
        ["   <pre>", "x", "   </pre>"],
        (mf.HTML_OPEN, mf.HTML_CONTENT, mf.HTML_CLOSE),
        None,
        None,
        id="pre_indent_3_opens",
    ),
    pytest.param(
        ["    <pre>"],
        (mf.TEXT,),
        None,
        None,
        id="pre_indent_4_stays_text",
    ),
    pytest.param(
        ["<details>", "<summary>x</summary>", "</details>"],
        (mf.TEXT, mf.TEXT, mf.TEXT),
        None,
        None,
        id="details_stays_text",
    ),
]


@pytest.mark.parametrize(
    "lines, expected_kinds, expected_unterminated_opener, expected_unterminated_html",
    CONTEXT_CENSUS,
)
def test_context_scan_census(
    lines, expected_kinds, expected_unterminated_opener, expected_unterminated_html,
):
    result = mf.scan_contexts(lines)
    assert result.kinds == expected_kinds
    assert set(result.kinds) <= mf.CONTEXT_KINDS
    for i, kind in enumerate(result.kinds):
        assert result.inert[i] == (kind != mf.TEXT)
    assert result.unterminated_opener_line == expected_unterminated_opener
    assert result.unterminated_html_line == expected_unterminated_html
