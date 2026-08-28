"""Spent probe (#1140 round 3) — neutralized.

This file briefly held a deliberate shipped-source-write probe used to earn a
receipt that the guard blocks and NAMES a violating test. That receipt is taken;
the probe body is removed so this disposable worktree cannot fail a later run.
"""


def test_probe_retired():
    assert True
