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
