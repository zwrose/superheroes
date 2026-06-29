// plugins/superheroes/lib/loop_synthesis.js
const { findingIdentity } = require('./circuit_breaker.js')
const _TIERS = new Set(['Critical', 'Important', 'Minor', 'Nit'])
const _BLOCKING = new Set(['Critical', 'Important'])
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
    const v = byId[id]
    const action = (v && typeof v === 'object') ? v.action : null
    const reason = (v && typeof v === 'object') ? v.reason : null
    if (action === 'drop' && typeof reason === 'string' && reason.trim()) {
      drops.push({ id, file: f.file === undefined ? null : f.file, title: f.title === undefined ? null : f.title,
        reason: reason.trim(), was_blocking_tagged: _BLOCKING.has(f.severity) })
      continue
    }
    const kept = Object.assign({}, f)
    const sev = (v && typeof v === 'object') ? v.severity : null
    if (_TIERS.has(sev)) kept.severity = sev
    survivors.push(kept)
  }
  return { findings: survivors, drops }
}
module.exports = { consume }
