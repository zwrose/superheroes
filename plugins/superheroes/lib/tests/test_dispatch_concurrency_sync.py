"""Drift guard for concurrent-dispatch doctrine across enumerated surfaces.

Guards that three canonical literals stay whitespace-run-tolerant and byte-exact in every other
respect across this **enumerated** surface list — not every place in the repo that mentions
parallel or concurrent dispatch; several other files bless parallelism in their own words and are
deliberately out of scope:

- ``rubric/launch-doctrine.md``
- ``skills/review-code/reference/round-driver.md``
- ``skills/workhorse/SKILL.md``

Overclaiming coverage in this docstring is the failure mode the enumeration exists to prevent.
"""
import os
import re

import pytest

import launch_doctrine as LD

_HERE = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_ROOT = os.path.normpath(os.path.join(_HERE, "..", ".."))

_SURFACES = (
    "rubric/launch-doctrine.md",
    "skills/review-code/reference/round-driver.md",
    "skills/workhorse/SKILL.md",
)

# Hard-coded oracle literals — §11 pattern-2 drift guards on RULING_INVARIANTS["await-dispatches"].
# Used only in test_ruling_invariants_pins_all_three_literals; per-surface checks read the home.
_TURN_END_SENTENCE = (
    'Ending the turn ends a headless session; "wait" must be an in-turn poll, never a final message.'
)
_INVARIANT_CLAUSE = (
    "in-turn awaiting only; never harness-external backgrounding (`&`/setsid/nohup), "
    "never an unwatched run-dir at turn end"
)
_INDEPENDENCE_TEST = (
    "no result dependency, no shared writable worktree, and no shared output path"
)

_PHRASE_BY_LABEL = {
    "invariant clause": _INVARIANT_CLAUSE,
    "independence test": _INDEPENDENCE_TEST,
    "turn-end sentence": _TURN_END_SENTENCE,
}

_EXPECTED_PHRASE_COUNT = len(_PHRASE_BY_LABEL)


def _read_plugin(rel):
    path = os.path.join(_PLUGIN_ROOT, rel)
    if not os.path.isfile(path):
        raise AssertionError(f"surface file missing or unreadable: {rel}")
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _normalize_for_line_wrap(text):
    """Collapse whitespace runs so hard-wrapped markdown still matches oracle literals.

    Line wrapping is a layout choice in hard-wrapped markdown and carries no meaning, so
    tolerating it is correct; every other difference still fails — a changed or inserted word,
    changed punctuation, curly quotes substituted for the straight quotes around "wait", an
    un-backticked &, or a partial match.
    """
    return re.sub(r"\s+", " ", text).strip()


def _literal_present(text, literal):
    return _normalize_for_line_wrap(literal) in _normalize_for_line_wrap(text)


def _phrase_equals_literal(phrase, literal):
    return _normalize_for_line_wrap(phrase) == _normalize_for_line_wrap(literal)


def _await_dispatches_phrases():
    invariants = LD.RULING_INVARIANTS
    if "await-dispatches" not in invariants:
        raise AssertionError(
            'RULING_INVARIANTS missing key "await-dispatches"'
        )
    phrases = invariants["await-dispatches"]
    if not isinstance(phrases, (tuple, list)):
        raise AssertionError(
            'RULING_INVARIANTS["await-dispatches"] must be a tuple or list, '
            f"got {type(phrases).__name__}"
        )
    if len(phrases) == 0:
        raise AssertionError(
            'RULING_INVARIANTS["await-dispatches"] must not be empty'
        )
    return phrases


def _assert_exact_await_dispatches_phrases(phrases):
    if len(phrases) != _EXPECTED_PHRASE_COUNT:
        raise AssertionError(
            'RULING_INVARIANTS["await-dispatches"] must have exactly '
            f"{_EXPECTED_PHRASE_COUNT} phrases, found {len(phrases)}: {phrases!r}"
        )
    normalized_found = {_normalize_for_line_wrap(p) for p in phrases}
    normalized_expected = {
        _normalize_for_line_wrap(literal) for literal in _PHRASE_BY_LABEL.values()
    }
    if normalized_found != normalized_expected:
        found_not_expected = normalized_found - normalized_expected
        expected_not_found = normalized_expected - normalized_found
        raise AssertionError(
            'RULING_INVARIANTS["await-dispatches"] must match the three expected '
            f"phrases exactly — found-not-expected: {sorted(found_not_expected)!r}, "
            f"expected-not-found: {sorted(expected_not_found)!r}"
        )


def _phrase_for_label(label):
    if label not in _PHRASE_BY_LABEL:
        raise AssertionError(f"unknown phrase label: {label!r}")
    literal = _PHRASE_BY_LABEL[label]
    for phrase in _await_dispatches_phrases():
        if _phrase_equals_literal(phrase, literal):
            return phrase
    normalized = _normalize_for_line_wrap(literal)
    raise AssertionError(
        f'{label!r} missing from RULING_INVARIANTS["await-dispatches"] '
        f"— expected exact phrase: {normalized!r}"
    )


def _workhorse_section7_concurrency_region():
    """§7 concurrency prose — not the whole file or the 'When you're tempted' table."""
    text = _read_plugin("skills/workhorse/SKILL.md")
    section = re.search(
        r"\*\*Await every dispatch in-turn\*\*.*?(?=^## 8\. )",
        text,
        re.MULTILINE | re.DOTALL,
    )
    assert section, (
        "workhorse/SKILL.md §7 concurrency region not found — anchor "
        "'**Await every dispatch in-turn**' through before '## 8.' missing or moved?"
    )
    return section.group(0)


def _surface_text(rel):
    if rel == "skills/workhorse/SKILL.md":
        return _workhorse_section7_concurrency_region()
    return _read_plugin(rel)


def _assert_literal_on_surface(rel, text, literal, label):
    normalized_literal = _normalize_for_line_wrap(literal)
    if not _literal_present(text, literal):
        raise AssertionError(
            f"{label!r} missing from {rel} — expected exact substring: {normalized_literal!r}"
        )


def _assert_literal_on_every_surface(literal, label):
    for rel in _SURFACES:
        text = _surface_text(rel)
        _assert_literal_on_surface(rel, text, literal, label)


@pytest.mark.parametrize("label", sorted(_PHRASE_BY_LABEL))
def test_literal_on_every_amended_surface(label):
    phrase = _phrase_for_label(label)
    _assert_literal_on_every_surface(phrase, label)


def test_ruling_invariants_pins_all_three_literals():
    # §11 pattern-2 drift guard: hand-typed literals must equal the machine home exactly.
    phrases = _await_dispatches_phrases()
    _assert_exact_await_dispatches_phrases(phrases)
    for label, literal in _PHRASE_BY_LABEL.items():
        normalized = _normalize_for_line_wrap(literal)
        if not any(_phrase_equals_literal(phrase, literal) for phrase in phrases):
            raise AssertionError(
                f'{label!r} missing from RULING_INVARIANTS["await-dispatches"] '
                f"— expected exact phrase: {normalized!r}"
            )
    result = LD.load()
    assert result["ok"] is True, (
        f"launch_doctrine.load() refused: reason={result.get('reason')!r}"
    )


def test_normalize_accepts_whitespace_rewrap():
    rewrapped = _INVARIANT_CLAUSE.replace("; ", ";\n")
    assert _literal_present(rewrapped, _INVARIANT_CLAUSE)


# Bite: changed word — must not match
def test_normalize_rejects_changed_word():
    mutated = _INVARIANT_CLAUSE.replace("unwatched", "watched")
    assert not _literal_present(mutated, _INVARIANT_CLAUSE)


# Bite: inserted word — must not match
def test_normalize_rejects_inserted_word():
    mutated = _INVARIANT_CLAUSE.replace("never an", "never quite an")
    assert not _literal_present(mutated, _INVARIANT_CLAUSE)


# Bite: changed punctuation — must not match
def test_normalize_rejects_changed_punctuation():
    mutated = _INVARIANT_CLAUSE.replace(";", ",")
    assert not _literal_present(mutated, _INVARIANT_CLAUSE)


# Bite: curly quotes around "wait" — must not match
def test_normalize_rejects_curly_quotes_around_wait():
    mutated = _TURN_END_SENTENCE.replace('"wait"', "\u201cwait\u201d")
    assert not _literal_present(mutated, _TURN_END_SENTENCE)


# Bite: un-backticked & — must not match
def test_normalize_rejects_unbackticked_ampersand():
    mutated = _INVARIANT_CLAUSE.replace("`&`", "&")
    assert not _literal_present(mutated, _INVARIANT_CLAUSE)


# Bite: truncated partial literal — must not match
def test_normalize_rejects_truncated_literal():
    mutated = _INVARIANT_CLAUSE[: len(_INVARIANT_CLAUSE) // 2]
    assert not _literal_present(mutated, _INVARIANT_CLAUSE)


# Bite: appended suffix — _phrase_equals_literal must reject containment
def test_phrase_equals_literal_rejects_appended_suffix():
    suffixed = _INVARIANT_CLAUSE + " except when the owner says otherwise"
    assert not _phrase_equals_literal(suffixed, _INVARIANT_CLAUSE)


# Bite: grown tuple — _assert_exact_await_dispatches_phrases must reject an extra phrase
def test_assert_exact_await_dispatches_phrases_rejects_grown_tuple():
    real_phrases = tuple(_PHRASE_BY_LABEL[label] for label in sorted(_PHRASE_BY_LABEL))
    grown = real_phrases + (
        "An extra plausible sentence that is not part of the canonical trio.",
    )
    with pytest.raises(AssertionError, match="must have exactly"):
        _assert_exact_await_dispatches_phrases(grown)


# Bite: duplicate-padded tuple — _assert_exact_await_dispatches_phrases must reject length mismatch
def test_assert_exact_await_dispatches_phrases_rejects_duplicate_padded_tuple():
    real_phrases = tuple(_PHRASE_BY_LABEL[label] for label in sorted(_PHRASE_BY_LABEL))
    padded = real_phrases + (real_phrases[0],)
    with pytest.raises(AssertionError, match="must have exactly"):
        _assert_exact_await_dispatches_phrases(padded)


# Bite: mutated phrase — _assert_exact_await_dispatches_phrases must reject a changed word
def test_assert_exact_await_dispatches_phrases_rejects_mutated_phrase():
    phrases = list(_PHRASE_BY_LABEL[label] for label in sorted(_PHRASE_BY_LABEL))
    for index, phrase in enumerate(phrases):
        if "unwatched" in phrase:
            phrases[index] = phrase.replace("unwatched", "watched")
            break
    with pytest.raises(AssertionError, match="found-not-expected"):
        _assert_exact_await_dispatches_phrases(tuple(phrases))
