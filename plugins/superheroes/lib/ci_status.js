// plugins/superheroes/lib/ci_status.js
const _PASS = new Set(['pass', 'success', 'skipping', 'skipped', 'neutral'])
function _bucket(item) {
  if (!item || typeof item !== 'object') return 'unknown'
  return String(item.bucket || item.state || item.conclusion || 'unknown').toLowerCase()
}
function classify(checks) {
  if (!Array.isArray(checks) || checks.length === 0) return { status: 'none', failing: [] }
  const failing = []
  let sawGating = false
  for (const item of checks) {
    const b = _bucket(item)
    const name = (item && typeof item === 'object') ? item.name : null
    if (b === 'skipping' || b === 'skipped' || b === 'neutral') continue
    sawGating = true
    if (!_PASS.has(b)) failing.push(name || 'unknown')
  }
  if (failing.length) return { status: 'red', failing }
  if (!sawGating) return { status: 'none', failing: [] }
  return { status: 'green', failing: [] }
}
module.exports = { classify }
