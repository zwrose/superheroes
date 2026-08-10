"""Drift guard for concurrent-dispatch doctrine across enumerated surfaces.

Guards that three canonical literals stay byte-identical across this **enumerated** surface
list — not every place in the repo that mentions parallel or concurrent dispatch; several other
files bless parallelism in their own words and are deliberately out of scope:

- ``rubric/launch-doctrine.md``
- ``skills/review-code/reference/round-driver.md``
- ``skills/workhorse/SKILL.md``

Overclaiming coverage in this docstring is the failure mode the enumeration exists to prevent.
"""
import os

import launch_doctrine as LD

_HERE = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_ROOT = os.path.normpath(os.path.join(_HERE, "..", ".."))

_SURFACES = (
    "rubric/launch-doctrine.md",
    "skills/review-code/reference/round-driver.md",
    "skills/workhorse/SKILL.md",
)

# Hard-coded oracle literals — not imported from launch_doctrine or any guarded file.
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


def _assert_literal_on_every_surface(literal, label):
    for rel in _SURFACES:
        text = _read_plugin(rel)
        if literal not in text:
            raise AssertionError(
                f"{label!r} missing from {rel} — expected exact substring: {literal!r}"
            )


def test_turn_end_sentence_on_every_amended_surface():
    _assert_literal_on_every_surface(_TURN_END_SENTENCE, "turn-end sentence")


def test_invariant_clause_on_every_amended_surface():
    _assert_literal_on_every_surface(_INVARIANT_CLAUSE, "invariant clause")


def test_independence_test_on_every_amended_surface():
    _assert_literal_on_every_surface(_INDEPENDENCE_TEST, "independence test")


def test_ruling_invariants_pins_all_three_literals():
    invariants = LD.RULING_INVARIANTS
    if "await-dispatches" not in invariants:
        raise AssertionError(
            'RULING_INVARIANTS missing key "await-dispatches"'
        )
    phrases = invariants["await-dispatches"]
    for literal, label in (
        (_TURN_END_SENTENCE, "turn-end sentence"),
        (_INVARIANT_CLAUSE, "invariant clause"),
        (_INDEPENDENCE_TEST, "independence test"),
    ):
        if not any(literal in phrase for phrase in phrases):
            raise AssertionError(
                f'{label!r} missing from RULING_INVARIANTS["await-dispatches"] '
                f"— expected exact substring: {literal!r}"
            )
    result = LD.load()
    assert result["ok"] is True, (
        f"launch_doctrine.load() refused: reason={result.get('reason')!r}"
    )
