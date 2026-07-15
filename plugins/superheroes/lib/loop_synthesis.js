// plugins/superheroes/lib/loop_synthesis.js
const { findingIdentity, isBlocking } = require('./circuit_breaker.js')
const _TIERS = new Set(['Critical', 'Important', 'Minor', 'Nit'])
const _DEFAULT_BLOCKING_SEVERITY = 'Important'
// #276: the blocking partition (was-tagged-blocking, blocking→non-blocking downgrade detection) routes
// through circuit_breaker.isBlocking — the single, case-normalized, fail-closed predicate — so this
// leg can never disagree with _partition / the breaker / the panel gate on what blocks.

function _keptSeverity(f, v) {
  const verdictSeverity = (v && typeof v === 'object') ? v.severity : null
  if (_TIERS.has(verdictSeverity)) return verdictSeverity
  if (_TIERS.has(f && f.severity)) return f.severity
  return _DEFAULT_BLOCKING_SEVERITY
}

function consume(merged, leafVerdicts) {
  const byId = Object.create(null)   // null-proto: byId[identity] tests own keys only (Python dict parity)
  // #430: track first-insertion order explicitly. Object.keys() would order integer-like string keys
  // numerically ascending — a drifted/mis-keyed verdict id COULD be integer-like ("42") — diverging
  // from Python's dict first-insertion iteration and breaking the consume parity goldens (§11).
  const idOrder = []
  if (Array.isArray(leafVerdicts)) {
    for (const v of leafVerdicts) {
      if (v && typeof v === 'object' && typeof v.id === 'string') {
        if (byId[v.id] === undefined) idOrder.push(v.id)
        byId[v.id] = v
      }
    }
  }
  const matchedIds = Object.create(null)   // #430: which verdict ids matched a finding
  const survivors = []; const drops = []; const downgrades = []
  for (const f of merged) {
    const id = findingIdentity(f)
    let v = byId[id]
    let matchedKey = (v !== undefined) ? id : null
    if (!v && f && typeof f.id === 'string') { v = byId[f.id]; if (v !== undefined) matchedKey = f.id }
    if (matchedKey !== null) matchedIds[matchedKey] = true
    const action = (v && typeof v === 'object') ? v.action : null
    const reason = (v && typeof v === 'object') ? v.reason : null
    if (action === 'drop' && typeof reason === 'string' && reason.trim()) {
      drops.push({ id, file: f.file === undefined ? null : f.file, title: f.title === undefined ? null : f.title,
        reason: reason.trim(), was_blocking_tagged: isBlocking(f.severity) })
      continue
    }
    const kept = Object.assign({}, f)
    kept.severity = _keptSeverity(f, v)
    survivors.push(kept)
    // DOWNGRADE-FLAG (#186): a survivor re-tiered from blocking to non-blocking rides recorded
    // (severity outcome unchanged) so the readout can flag it like a dropped blocker.
    const fromSeverity = f && f.severity
    if (isBlocking(fromSeverity) && !isBlocking(kept.severity)) {
      const entry = { id, file: f.file === undefined ? null : f.file,
        title: f.title === undefined ? null : f.title, from: fromSeverity, to: kept.severity }
      if (typeof reason === 'string' && reason.trim()) entry.reason = reason.trim()
      downgrades.push(entry)
    }
  }
  const unmatched = idOrder.filter((vid) => !matchedIds[vid])
  return { findings: survivors, drops, downgrades, unmatched }
}
module.exports = { consume }
