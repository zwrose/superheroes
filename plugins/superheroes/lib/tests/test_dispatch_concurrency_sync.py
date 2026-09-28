"""Drift guard for concurrent-dispatch doctrine across enumerated surfaces.

Guards that three canonical literals stay whitespace-run-tolerant and byte-exact in every other
respect across this **enumerated** surface list — not every place in the repo that mentions
parallel or concurrent dispatch; several other files bless parallelism in their own words and are
deliberately out of scope:

- ``rubric/launch-doctrine.md``
- ``skills/review-code/reference/round-driver.md``
- ``skills/workhorse/SKILL.md``

Overclaiming coverage in this docstring is the failure mode the enumeration exists to prevent.

What is guaranteed is **presence** of each canonical literal verbatim modulo line wrapping on
every enumerated surface. The guard does **not** detect a literal that is present but neutralized
by surrounding prose (for example an appended exception clause); that semantic check is
deliberately out of scope and tracked as a follow-up.
"""
import os
import re

import pytest

import launch_doctrine as LD

_HERE = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_ROOT = os.path.normpath(os.path.join(_HERE, "..", ".."))

_SURFACES = (
    "rubric/launch-doctrine.md",
    "skills/review-code/reference/auto-fix-loop.md",
    "skills/review-code/reference/round-driver.md",
    "skills/workhorse/SKILL.md",
)
# auto-fix-loop.md carries only the channel-ownership sentence and points at the ruling's home.
_RULING_PHRASE_SURFACES = tuple(
    rel for rel in _SURFACES if rel != "skills/review-code/reference/auto-fix-loop.md"
)
assert len(_RULING_PHRASE_SURFACES) == 3, (
    f"_RULING_PHRASE_SURFACES must have exactly 3 entries, got {len(_RULING_PHRASE_SURFACES)}"
)

_CHANNEL_OWNERSHIP_SENTENCE = (
    "`await-dispatches` ruling governs the **channel** for dispatches the **builder itself** launches."
)
_CHANNEL_OWNERSHIP_LABEL = "channel ownership"
_CHANNEL_OWNERSHIP_SURFACES = (
    "skills/review-code/reference/auto-fix-loop.md",
    "skills/workhorse/SKILL.md",
)
_CHANNEL_OWNERSHIP_SURFACE_OVERRIDES = {
    "skills/review-code/reference/auto-fix-loop.md": (
        "`await-dispatches` ruling governs the **channel** for dispatches "
        "**the builder itself launches**."
    ),
}


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


def _canonical_await_dispatches_phrases():
    return tuple(_await_dispatches_phrases())


def _await_dispatches_phrase_label(index):
    return f"await-dispatches[{index}]"


def _await_dispatches_index_from_label(label):
    prefix = "await-dispatches["
    if not label.startswith(prefix) or not label.endswith("]"):
        raise AssertionError(f"not an await-dispatches phrase label: {label!r}")
    index_text = label[len(prefix) : -1]
    if not index_text.isdigit():
        raise AssertionError(f"not an await-dispatches phrase label: {label!r}")
    return int(index_text)


def _surface_check_cases():
    cases = []
    for index, phrase in enumerate(_await_dispatches_phrases()):
        cases.append((_await_dispatches_phrase_label(index), phrase))
    cases.append((_CHANNEL_OWNERSHIP_LABEL, _CHANNEL_OWNERSHIP_SENTENCE))
    return tuple(cases)


_SURFACE_CHECK_CASES = _surface_check_cases()


def _assert_exact_await_dispatches_phrases(phrases):
    canonical = _canonical_await_dispatches_phrases()
    if len(phrases) != len(canonical):
        raise AssertionError(
            'RULING_INVARIANTS["await-dispatches"] must have exactly '
            f"{len(canonical)} phrases, found {len(phrases)}: {phrases!r}"
        )
    normalized_found = {_normalize_for_line_wrap(p) for p in phrases}
    normalized_canonical = {_normalize_for_line_wrap(p) for p in canonical}
    if normalized_found != normalized_canonical:
        found_not_expected = normalized_found - normalized_canonical
        expected_not_found = normalized_canonical - normalized_found
        raise AssertionError(
            'RULING_INVARIANTS["await-dispatches"] must match the ruling-invariant '
            f"phrases exactly — found-not-expected: {sorted(found_not_expected)!r}, "
            f"expected-not-found: {sorted(expected_not_found)!r}"
        )


def _workhorse_section7_body():
    """Full §7 body — channel-ownership prose sits above the concurrency anchor."""
    text = _read_plugin("skills/workhorse/SKILL.md")
    section = re.search(
        r"^## 7\. Delegate every implementation.*?(?=^## 8\. )",
        text,
        re.MULTILINE | re.DOTALL,
    )
    assert section, (
        "workhorse/SKILL.md §7 body not found — anchor "
        "'## 7. Delegate every implementation' through before '## 8.' missing or moved?"
    )
    return section.group(0)


def _workhorse_section7_concurrency_region():
    """§7 concurrency prose — not the whole file or the 'When you're tempted' table."""
    text = _workhorse_section7_body()
    section = re.search(
        r"\*\*Await every dispatch in-turn\*\*.*?(?=^## 8\. |\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    assert section, (
        "workhorse/SKILL.md §7 concurrency region not found — anchor "
        "'**Await every dispatch in-turn**' through before '## 8.' missing or moved?"
    )
    return section.group(0)


def _literal_for_surface(rel, label):
    if label == _CHANNEL_OWNERSHIP_LABEL:
        literal = _CHANNEL_OWNERSHIP_SENTENCE
    else:
        index = _await_dispatches_index_from_label(label)
        phrases = _await_dispatches_phrases()
        if index >= len(phrases):
            raise AssertionError(
                f'{label!r}: RULING_INVARIANTS["await-dispatches"] has only {len(phrases)} '
                f"phrase(s), need index {index}"
            )
        literal = phrases[index]
    if label == _CHANNEL_OWNERSHIP_LABEL:
        return _CHANNEL_OWNERSHIP_SURFACE_OVERRIDES.get(rel, literal)
    return literal


def _surface_text(rel, label=None):
    if rel == "skills/workhorse/SKILL.md":
        if label == _CHANNEL_OWNERSHIP_LABEL:
            return _workhorse_section7_body()
        return _workhorse_section7_concurrency_region()
    return _read_plugin(rel)


def _assert_literal_on_surface(rel, text, literal, label):
    normalized_literal = _normalize_for_line_wrap(literal)
    if not _literal_present(text, literal):
        raise AssertionError(
            f"{label!r} missing from {rel} — expected exact substring: {normalized_literal!r}"
        )


def _assert_literal_on_every_surface(literal, label):
    surfaces = (
        _CHANNEL_OWNERSHIP_SURFACES
        if label == _CHANNEL_OWNERSHIP_LABEL
        else _RULING_PHRASE_SURFACES
    )
    for rel in surfaces:
        surface_literal = _literal_for_surface(rel, label)
        text = _surface_text(rel, label)
        _assert_literal_on_surface(rel, text, surface_literal, label)


@pytest.mark.parametrize(
    "label,phrase",
    _SURFACE_CHECK_CASES,
    ids=[case[0] for case in _SURFACE_CHECK_CASES],
)
def test_literal_on_every_amended_surface(label, phrase):
    _assert_literal_on_every_surface(phrase, label)


def test_ruling_invariants_pins_all_await_dispatches_literals():
    result = LD.load()
    assert result["ok"] is True, (
        f"launch_doctrine.load() refused: reason={result.get('reason')!r}"
    )
    _assert_exact_await_dispatches_phrases(tuple(_await_dispatches_phrases()))


def test_normalize_accepts_whitespace_rewrap():
    invariant_clause = _await_dispatches_phrases()[0]
    rewrapped = invariant_clause.replace("; ", ";\n")
    assert _literal_present(rewrapped, invariant_clause)


# Bite: changed word — must not match
def test_normalize_rejects_changed_word():
    invariant_clause = _await_dispatches_phrases()[0]
    mutated = invariant_clause.replace("unwatched", "watched")
    assert not _literal_present(mutated, invariant_clause)


# Bite: inserted word — must not match
def test_normalize_rejects_inserted_word():
    invariant_clause = _await_dispatches_phrases()[0]
    mutated = invariant_clause.replace("never an", "never quite an")
    assert not _literal_present(mutated, invariant_clause)


# Bite: changed punctuation — must not match
def test_normalize_rejects_changed_punctuation():
    invariant_clause = _await_dispatches_phrases()[0]
    mutated = invariant_clause.replace(";", ",")
    assert not _literal_present(mutated, invariant_clause)


# Bite: curly quotes around "wait" — must not match
def test_normalize_rejects_curly_quotes_around_wait():
    turn_end = _await_dispatches_phrases()[2]
    mutated = turn_end.replace('"wait"', "\u201cwait\u201d")
    assert not _literal_present(mutated, turn_end)


# Bite: un-backticked & — must not match
def test_normalize_rejects_unbackticked_ampersand():
    invariant_clause = _await_dispatches_phrases()[0]
    mutated = invariant_clause.replace("`&`", "&")
    assert not _literal_present(mutated, invariant_clause)


# Bite: truncated partial literal — must not match
def test_normalize_rejects_truncated_literal():
    invariant_clause = _await_dispatches_phrases()[0]
    mutated = invariant_clause[: len(invariant_clause) // 2]
    assert not _literal_present(mutated, invariant_clause)


# Bite: appended suffix — _phrase_equals_literal must reject containment
def test_phrase_equals_literal_rejects_appended_suffix():
    invariant_clause = _await_dispatches_phrases()[0]
    suffixed = invariant_clause + " except when the owner says otherwise"
    assert not _phrase_equals_literal(suffixed, invariant_clause)


# Bite: grown tuple — _assert_exact_await_dispatches_phrases must reject an extra phrase
def test_assert_exact_await_dispatches_phrases_rejects_grown_tuple():
    real_phrases = _canonical_await_dispatches_phrases()
    grown = real_phrases + (
        "An extra plausible sentence that is not part of the canonical trio.",
    )
    with pytest.raises(AssertionError, match="must have exactly"):
        _assert_exact_await_dispatches_phrases(grown)


# Bite: duplicate-padded tuple — _assert_exact_await_dispatches_phrases must reject length mismatch
def test_assert_exact_await_dispatches_phrases_rejects_duplicate_padded_tuple():
    real_phrases = _canonical_await_dispatches_phrases()
    padded = real_phrases + (real_phrases[0],)
    with pytest.raises(AssertionError, match="must have exactly"):
        _assert_exact_await_dispatches_phrases(padded)


# Bite: mutated phrase — _assert_exact_await_dispatches_phrases must reject a changed word
def test_assert_exact_await_dispatches_phrases_rejects_mutated_phrase():
    phrases = list(_canonical_await_dispatches_phrases())
    for index, phrase in enumerate(phrases):
        if "unwatched" in phrase:
            phrases[index] = phrase.replace("unwatched", "watched")
            break
    with pytest.raises(AssertionError, match="found-not-expected"):
        _assert_exact_await_dispatches_phrases(tuple(phrases))
