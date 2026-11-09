"""#2398 (V856-3, vet 856 on PR #2391): a title word counts as that word only where GitHub shows a word break after it. A word
whose end GitHub runs into the next word through inline markup (emphasis, strikethrough, a code span, an inline link, an HTML
tag) is not that word: ``off*f*`` is shown ``offf``, so the acceptance does not carry the title word ``off``. The check is
``leftover_accepting._names`` (the one chokepoint of the title compare, via ``_mark_glued_ends``); the id compare is not touched.

Render oracle. Rows marked ``github`` carry vet 856's GitHub renders (``*f*``, `` `f` `` and ``[f](url)`` after the last
word show ``offf``). Every other row is ``model-only``: the dispatcher (not the implementer) checked those rows against a local
CommonMark renderer (markdown-it 4.2.0) and GFM's spec, because GitHub's ``POST /markdown`` was unreachable from the build
session. Each parametrized row's id names its render.

The bite-proof record is ``bite_proofs/i2398_leftover_title_word_end.md``."""
import unicodedata

import pytest

import leftover_accepting as la
from test_leftover_rule_2332 import rec, gaps

TITLE = "The retry loop never backs off"
RECORD = rec(("F-1", TITLE))

# (id, the text glued to the last title word); each shows the last word joined to an `f`
GLUES = [
    pytest.param("*f*", id="emphasis_shows_offf_github"),
    pytest.param("`f`", id="code_span_shows_offf_github"),
    pytest.param("[f](https://x.example)", id="link_shows_offf_github"),
    pytest.param("<b>f</b>", id="tag_shows_offf_model_only"),
]


# --- 1 and 2: the four refusal rows, end to end and at the chokepoint ------------------------------

@pytest.mark.parametrize("glue", GLUES)
def test_a_title_word_glued_to_markup_is_not_that_word_end_to_end(glue):
    assert gaps(RECORD, "- F-1 The retry loop never backs off%s: accepted.\n" % glue) == ["F-1"]


@pytest.mark.parametrize("glue", GLUES)
def test_a_title_word_glued_to_markup_is_not_that_word_at_the_chokepoint(glue):
    # `_names` is called directly, so the tag row is proven at the check itself (end to end `_scan_line` cuts it first)
    assert la._names("F-1 The retry loop never backs off%s: accepted." % glue, "F-1", TITLE) is False


def test_a_link_with_a_title_is_not_glued_at_the_chokepoint():
    # chokepoint only: end to end, md_hidden reads a line holding a link title as unsure and `_cut_items` blanks the item first (upstream, outside #2398)
    assert la._names("F-1 [The retry loop never backs off](https://x.example 'note') accepted.", "F-1", TITLE) is True


# --- 3: more glued forms that must refuse ----------------------------------------------------------

@pytest.mark.parametrize("line", [
    pytest.param("- F-1 The retry loop never backs off` f `: accepted.\n", id="padded_code_span_shows_offf_model_only"),
    pytest.param("- F-1 The retry loop never backs off~~f~~: accepted.\n", id="strikethrough_shows_offf_model_only"),
    pytest.param("- F-1 The retry loop never backs off**f**: accepted.\n", id="strong_shows_offf_model_only"),
    pytest.param("- F-1 *The retry loop never backs off*f: accepted.\n", id="closing_emphasis_shows_offf_model_only"),
    pytest.param("- F-1 `The retry loop never backs off`f: accepted.\n", id="closing_code_span_shows_offf_model_only"),
    pytest.param("- F-1 [The retry loop never backs off](https://x.example)f: accepted.\n",
                 id="closing_link_shows_offf_model_only"),
    pytest.param("- F-1 The retry loop never*backs* off: accepted.\n", id="interior_emphasis_shows_neverbacks_model_only"),
    pytest.param("- F-1 The retry loop never backs off[f](<https://x.example>): accepted.\n",
                 id="angle_destination_link_shows_offf_model_only"),
    pytest.param("- F-1 The retry loop never backs off[f](https://x.example/a_(b)): accepted.\n",
                 id="parenthesised_destination_link_shows_offf_model_only"),
    # review round 1, v1: GFM link text nests balanced brackets, so this is one link (shown `off<a>f [g]</a>`)
    pytest.param("- F-1 The retry loop never backs off[f [g]](https://x.example): accepted.\n",
                 id="balanced_brackets_in_link_text_shows_offf_model_only"),
    # review round 1, v5: CommonMark strips the padding of ` off `, so the span's shown content ends at `off` (`<code>…off</code>f`)
    pytest.param("- F-1 ` The retry loop never backs off `f: accepted.\n", id="padded_closing_code_span_shows_offf_model_only"),
])
def test_more_glued_forms_are_refused(line):
    assert gaps(RECORD, line) == ["F-1"]


# --- 4: healthy controls that must keep counting ---------------------------------------------------

@pytest.mark.parametrize("line", [
    pytest.param("- F-1 The retry loop never backs off now: accepted.\n", id="space_after"),
    pytest.param("- F-1 The retry loop never backs off\n", id="end_of_line"),
    pytest.param("- F-1 The retry loop never backs off.\n", id="period_after"),
    pytest.param("- F-1 (The retry loop never backs off) accepted.\n", id="closing_paren_after"),
    pytest.param("- F-1 **The retry loop never backs off**.\n", id="emphasis_wrapped"),
    pytest.param("- F-1 [The retry loop never backs off](https://x.example) accepted.\n", id="link_wrapped"),
    pytest.param("- F-1 `The retry loop never backs off`: accepted.\n", id="code_wrapped"),
    pytest.param("- F-1 `The retry loop never backs off*f*`: accepted.\n", id="stars_inside_a_code_span_are_literal"),
    pytest.param("- F-1 The retry loop never backs off*f: accepted.\n", id="unpaired_star_is_literal"),
    pytest.param("- F-1 The retry loop never backs off` f`: accepted.\n", id="code_span_content_starts_with_a_space"),
    pytest.param("- F-1 The retry loop never backs off`  f  `: accepted.\n", id="code_span_two_spaces_one_stripped"),
    pytest.param("- F-1 The retry loop never backs off*.*: accepted.\n", id="star_dot_star_is_literal"),
    pytest.param("- F-1 x*The* retry loop never backs off.\n", id="word_glued_at_its_start_is_unaffected"),
    # review round 1, v2: a fenced line is shown literally, so its stars are visible punctuation after `off`
    pytest.param("- F-1\n  ~~~\n  The retry loop never backs off*f*: accepted.\n  ~~~\n", id="stars_on_a_fenced_line_are_literal"),
    pytest.param("- F-1\n  ~~~\n  The retry loop never backs off[f](https://x.example)\n  ~~~\n",
                 id="link_on_a_fenced_line_is_literal"),
])
def test_healthy_acceptances_keep_counting(line):
    assert gaps(RECORD, line) == []


# --- fail-closed edges: literal markers and non-markup never glue ---------------------------------

@pytest.mark.parametrize("glue", [
    pytest.param("`f", id="unclosed_backtick_is_literal"),
    pytest.param("~~~f~~~", id="three_tildes_are_literal"),
    pytest.param("[f", id="bracket_without_a_link_is_literal"),
    pytest.param("<3", id="lt_not_a_tag"),
])
def test_literal_text_after_the_last_word_does_not_glue(glue):
    assert la._names("F-1 The retry loop never backs off%s: accepted." % glue, "F-1", TITLE) is True


def test_a_word_end_at_the_end_of_the_text_and_an_empty_text_are_unchanged():
    assert la._mark_glued_ends("off") == "off"
    assert la._mark_glued_ends("") == ""


# --- 5: monotonicity -------------------------------------------------------------------------------

def test_an_acceptance_that_did_not_count_at_base_still_does_not():
    assert gaps(RECORD, "- F-1 The retry loop never back*s* off: accepted.\n") == ["F-1"]


# --- 6: a title written with glued markup matches its verbatim copy --------------------------------

def test_a_title_written_with_glued_markup_matches_its_verbatim_copy_and_not_the_rendered_words():
    record = rec(("F-1", "The retry loop never backs off*f*"))
    assert gaps(record, "- F-1 The retry loop never backs off*f*: accepted.\n") == []
    assert gaps(record, "- F-1 The retry loop never backs off f: accepted.\n") == ["F-1"]


# --- 7: the marker ---------------------------------------------------------------------------------

def test_the_marker_is_a_word_character_that_normalisation_leaves_alone():
    marker = "ꙮ"
    assert la._MARKER == marker
    assert marker.isalnum()
    assert unicodedata.normalize("NFKC", marker) == marker
    assert marker.casefold() == marker
