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


def test_turn_end_sentence_on_every_amended_surface():
    phrases = _await_dispatches_phrases()
    _assert_literal_on_every_surface(phrases[2], "turn-end sentence")


def test_invariant_clause_on_every_amended_surface():
    phrases = _await_dispatches_phrases()
    _assert_literal_on_every_surface(phrases[0], "invariant clause")


def test_independence_test_on_every_amended_surface():
    phrases = _await_dispatches_phrases()
    _assert_literal_on_every_surface(phrases[1], "independence test")


def test_ruling_invariants_pins_all_three_literals():
    # §11 pattern-2 drift guard: hand-typed literals must equal the machine home exactly.
    phrases = _await_dispatches_phrases()
    for literal, label in (
        (_TURN_END_SENTENCE, "turn-end sentence"),
        (_INVARIANT_CLAUSE, "invariant clause"),
        (_INDEPENDENCE_TEST, "independence test"),
    ):
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
