// plugins/superheroes/lib/ci_status.js
// Parity twin of ci_status.py — green / red / pending / none. Pending is its own status
// (0.10.0 qualification finding: pending-as-red made the ship loop dispatch a CI fixer at
// checks that were merely running). Pending means WAIT, red means FIX, neither is green.
const _PASS = new Set(['pass', 'success', 'skipping', 'skipped', 'neutral'])
const _PENDING = new Set(['pending', 'queued', 'in_progress', 'expected', 'waiting', 'requested'])
function _bucket(item) {
  if (!item || typeof item !== 'object') return 'unknown'
  return String(item.bucket || item.state || item.conclusion || 'unknown').toLowerCase()
}
function classify(checks) {
  if (!Array.isArray(checks) || checks.length === 0) return { status: 'none', failing: [], pending: [] }
  const failing = []
  const pending = []
  let sawGating = false
  for (const item of checks) {
    const b = _bucket(item)
    const name = (item && typeof item === 'object') ? item.name : null
    if (b === 'skipping' || b === 'skipped' || b === 'neutral') continue
    sawGating = true
    if (_PASS.has(b)) continue
    if (_PENDING.has(b)) pending.push(name || 'unknown')
    else failing.push(name || 'unknown')
  }
  if (failing.length) return { status: 'red', failing, pending }
  if (pending.length) return { status: 'pending', failing: [], pending }
  if (!sawGating) return { status: 'none', failing: [], pending: [] }
  return { status: 'green', failing: [], pending: [] }
}
module.exports = { classify }
