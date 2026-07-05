# CLAUDE.md — failure-modes eval fixture

Conventions the review-crew agents calibrate against for this fixture.

## Transactions
Multi-step writes that must land together use the data layer's transaction:
`db.transaction(async (tx) => { ... })`. A sequence of dependent `db.*.update`
calls outside a transaction is a partial-failure bug.

## Outbound calls
All outbound HTTP goes through `retryFetch(url, { timeoutMs, retries })` from
`src/lib/retry-fetch.ts` — it enforces a timeout and bounded retries. Raw
`fetch` in service code has no timeout and no failure story.

## Migrations
Every migration module exports BOTH `up()` and `down()`. Destructive steps
(dropping or unsetting the old field) belong in a LATER migration, after a
verification window — never in the same pass that writes the new field.

## Concurrency
This is a multi-tenant service; any handler can run concurrently with itself.
Check-then-act flows on shared rows need an atomic guard (compare-and-set
filter, unique constraint, or a transaction with the read inside).

## Safety gates
Gates that decide whether a risky action proceeds (risk/limit/approval checks)
fail CLOSED: an absent, unknown, or unavailable signal must BLOCK the action,
never default to allow. A gate that returns "permit" on a missing/undefined
signal is a fail-direction bug.

## Queue / transport payloads
A record that crosses a serialization boundary (queue, outbox, worker
re-parse) is validated and bounded on the receiving side before it drives a
write — the consumer does not trust re-serialized fields as-is. A malformed or
partial message fails closed (is rejected), never applied on best-effort
defaults. A raw `JSON.parse` of a queue message with no schema/bounds check and
no fidelity verification is a transport-contract bug.
