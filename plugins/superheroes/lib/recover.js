// plugins/superheroes/lib/recover.js
const _UNKNOWN = 'unknown'
function _branchHash(branch) {
  if (typeof branch !== 'string' || !branch.includes('-')) return null
  return branch.slice(branch.lastIndexOf('-') + 1)
}
function reconcile(checkpoint, world) {
  world = world || {}
  if (world.store_ok === false) {
    return { action: 'park_gate', reason: 'control-plane store unusable — fail closed (no lockless run)' }
  }
  if (!checkpoint) return { action: 'world_derive', reason: 'no checkpoint — re-derive from reality' }
  if (checkpoint._incompatible) {
    // Match Python checkpoint.get("reason", "unknown reason"): default ONLY when the key is absent;
    // a present-but-falsy reason ("") is emitted as-is. (`|| 'unknown reason'` would wrongly substitute.)
    return { action: 'park_gate', reason: 'checkpoint incompatible — ' + (checkpoint.reason === undefined ? 'unknown reason' : checkpoint.reason) }
  }
  if (checkpoint.branch) {
    const cur = world.current_content_hash
    if (cur === null || cur === undefined) {
      return { action: 'gate', reason: 'could not recompute the tasks content-hash (transient) — not resuming blind' }
    }
    const bh = _branchHash(checkpoint.branch)
    if (bh !== null && bh !== cur) {
      return { action: 'gate', reason: 'approved tasks changed since this run started (stale spec)' }
    }
  }
  const pr = world.pr
  if (pr && typeof pr === 'object' && String(pr.state).toLowerCase() === 'merged') {
    return { action: 'gate', reason: "PR already merged — the work is done (merge is the owner's)" }
  }
  if (pr === _UNKNOWN) {
    return { action: 'gate', reason: 'could not read PR state (transient) — not creating a second PR' }
  }
  if (world.seeded_empty === _UNKNOWN) {
    return { action: 'gate', reason: 'could not read seeded state (transient) — cannot confirm a clean baseline' }
  }
  return { action: 'continue', from_step: checkpoint.lastGoodStep === undefined ? null : checkpoint.lastGoodStep, reason: 'reconciled — resume' }
}
function prAction(world) {
  const pr = (world || {}).pr
  if (pr === _UNKNOWN) return 'gate'
  if (pr && typeof pr === 'object' && !Array.isArray(pr)) {
    if (!pr.number) return 'gate'
    return String(pr.state).toLowerCase() === 'merged' ? 'gate' : 'adopt'
  }
  if (pr !== null && pr !== undefined) return 'gate'
  return 'create'
}
const FLOOR_RETRY_MAX = 3
function rearmAction(attempt, armed, maxRetry = FLOOR_RETRY_MAX) {
  if (armed) return 'proceed'
  if (attempt < maxRetry) return 'retry'
  return 'park_gate'
}
module.exports = { reconcile, prAction, rearmAction, FLOOR_RETRY_MAX }
