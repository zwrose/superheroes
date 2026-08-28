# Test-receipt evidence

This file is the **one home** for what artifacts ground a test-pass claim. Consumers point here
rather than restating the policy.

## Verify receipt is not a test receipt

A green verify exit is **not** evidence the test suite passed — calibration may run no tests at all.
A verify receipt does **not** ground a claim that tests passed.

## What does ground a test-pass claim

For test-pass claims, look for **CI** (named workflow + head sha) or the **build's ordered suite run**.
