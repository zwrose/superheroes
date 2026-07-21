# CLAUDE.md — high-noise eval fixture

Conventions the review-crew agents calibrate against for this fixture.

## The diff is the complete universe
Everything this change references exists in the diff. If a caller, guard,
wrapper, helper, or transaction is not visible there, it does not exist — and
every call site of a **module-local** (non-exported) helper is visible in the
file that declares it. Exported functions are a module's public API: routing and
wiring consume them outside this change, so an export with no call site in the
diff is not dead code.

## Deployment shape
One deployment serves many workspaces. Every request carries a server-verified
session with a `workspaceId`, and handlers are invoked concurrently by
principals from different workspaces.

## Ownership-scoped queries
Documents and export jobs are workspace-scoped. Every read, update, and delete of
a single record MUST match on BOTH the record id AND
`workspaceId: session.workspaceId`. Matching by id alone is a cross-workspace
access bug. The workspace filter is the primary defense and is sufficient on its
own — no second per-user check is required on top of it.

## Response payloads
All user-facing responses go through the helpers in `src/handlers/responses.ts`
(`ok`, `notFound`, `unauthorized`). Never hardcode an error string or build an
inline error payload in a handler — use the matching helper.

## Data access
Handlers call the data layer directly; this service has no repository layer, and
data access in a handler is the documented shape. `db.query(...)` uses `?`
placeholders and the data layer escapes every bound value, so passing user input
as a bound parameter is safe.

## Transactions
Multi-step writes that must land together use the data layer's transaction:
`db.transaction(async (tx) => { ... })`. A mid-flow crash inside the callback
rolls the whole transaction back. A sequence of dependent `db.*` writes outside a
transaction has no such story.

## Outbound calls
All outbound HTTP goes through `retryFetch(url, { timeoutMs, retries })`, defined
at the top of `src/services/publish.ts` — it bounds each attempt with a timeout
and caps the retries. A non-GET outbound call that may be retried also carries an
`Idempotency-Key` header derived from the durable identity of the operation (for
CDN publish: `cdn-publish:${workspaceId}:${id}`), so a retry cannot double-apply.

## Migrations
Every migration module exports BOTH `up()` and `down()`. A field swap is
additive first: write the new field and leave the legacy one in place; the
destructive half belongs to a later pass after a verification window.

## Formatting
Prettier runs on every commit through the pre-commit hook. Line width,
indentation, and spacing are the formatter's, and it rewrites them on the way in.
