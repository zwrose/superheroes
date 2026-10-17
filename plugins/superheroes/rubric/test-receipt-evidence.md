# Test-receipt evidence

This file is the **one home** for what artifacts ground a test-pass claim. Consumers point here
rather than restating the policy.

## Verify receipt is not a test receipt

A green verify exit is **not** evidence the test suite passed — calibration may run no tests at all.
A verify receipt does **not** ground a claim that tests passed.

## What does ground a test-pass claim

For test-pass claims, look for a **successful** CI conclusion for the named workflow on the exact
head sha (with evidence it runs the claimed tests) or the build's **ordered suite run** with the
command, raw output, and successful exit/pass summary. A failed, cancelled, or skipped CI run — or a
suite run ending in failures — does not ground the claim.

## A local pass the CI runner cannot reproduce

A test that commits in a temporary git repository sets the identity inline
(`-c user.name=… -c user.email=…`). A CI runner has no git identity, so a test that leans on yours
passes locally and fails in CI.

## Structured gate receipts

A project's verify command may also emit a structured receipt. The format's one home is `reference/gate-receipt.md`. The receipt's `result` is still not a test receipt unless the project's own policy says what it ran.
