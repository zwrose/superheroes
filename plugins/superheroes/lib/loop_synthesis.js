// plugins/superheroes/lib/loop_synthesis.js
const { findingIdentity } = require('./circuit_breaker.js')
const _TIERS = new Set(['Critical', 'Important', 'Minor', 'Nit'])
const _BLOCKING = new Set(['Critical', 'Important'])
const _DEFAULT_BLOCKING_SEVERITY = 'Important'

function _keptSeverity(f, v) {
  const verdictSeverity = (v && typeof v === 'object') ? v.severity : null
  if (_TIERS.has(verdictSeverity)) return verdictSeverity
  if (_TIERS.has(f && f.severity)) return f.severity
  return _DEFAULT_BLOCKING_SEVERITY
}

function consume(merged, leafVerdicts) {
  const byId = Object.create(null)   // null-proto: byId[identity] tests own keys only (Python dict parity)
  if (Array.isArray(leafVerdicts)) {
    for (const v of leafVerdicts) {
      if (v && typeof v === 'object' && typeof v.id === 'string') byId[v.id] = v
    }
  }
  const survivors = []; const drops = []
  for (const f of merged) {
    const id = findingIdentity(f)
    let v = byId[id]
    if (!v && f && typeof f.id === 'string') v = byId[f.id]
    const action = (v && typeof v === 'object') ? v.action : null
    const reason = (v && typeof v === 'object') ? v.reason : null
    if (action === 'drop' && typeof reason === 'string' && reason.trim()) {
      drops.push({ id, file: f.file === undefined ? null : f.file, title: f.title === undefined ? null : f.title,
        reason: reason.trim(), was_blocking_tagged: _BLOCKING.has(f.severity) })
      continue
    }
    const kept = Object.assign({}, f)
    kept.severity = _keptSeverity(f, v)
    survivors.push(kept)
  }
  return { findings: survivors, drops }
}
module.exports = { consume }
