"""Drift guard for a driver-mandate fact across enumerated surfaces (CONVENTIONS §11.2 pattern 2).

Guards one pinned clause: BACKGROUNDABLE_VERIFY, on
``skills/review-code/reference/round-driver.md`` and ``skills/workhorse/SKILL.md`` (symmetric
two-surface pin: whole-file count == 1 on each copy-holder; neither surface is authoritative).

What is guaranteed is **presence** of the pinned literal verbatim modulo ``*``-stripping and
whitespace collapse. It is pinned **whole-file** because its surfaces carry `` ``` `` fences
inside section-scoped regions.

The guard does **not** detect a literal that is present but neutralized by surrounding prose;
that semantic check is deliberately out of scope.
"""
import os

import pytest

from test_charter_boundary_sync import _normalized

_HERE = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_ROOT = os.path.normpath(os.path.join(_HERE, "..", ".."))

_BACKGROUNDABLE_VERIFY = (
    "The verify step may run harness-backgrounded and polled in-turn — the already-sanctioned "
    "shape for long local work — because the host's foreground command-timeout cap bounds a "
    "single call, not the step; what stays forbidden is unchanged, `&`/setsid/nohup and ending "
    "the turn to wait."
)

_BACKGROUNDABLE_VERIFY_SURFACES = [
    "skills/review-code/reference/round-driver.md",
    "skills/workhorse/SKILL.md",
]


def _read(rel):
    path = os.path.join(_PLUGIN_ROOT, rel)
    if not os.path.isfile(path):
        raise AssertionError(f"surface file missing or unreadable: {rel}")
    with open(path, encoding="utf-8") as fh:
        return fh.read()


@pytest.mark.parametrize(
    "rel",
    _BACKGROUNDABLE_VERIFY_SURFACES,
    ids=["round-driver", "workhorse"],
)
def test_backgroundable_verify_present(rel):
    # axis: presence of BACKGROUNDABLE_VERIFY literal whole-file, exactly once
    normalized_file = _normalized(_read(rel))
    normalized_literal = _normalized(_BACKGROUNDABLE_VERIFY)
    count = normalized_file.count(normalized_literal)
    assert count == 1, (
        f"expected exactly one occurrence in {rel}, found {count}"
    )

