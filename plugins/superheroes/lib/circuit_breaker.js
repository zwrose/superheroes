// plugins/superheroes/lib/circuit_breaker.js
const BLOCKING = new Set(['Critical', 'Important'])
// Python re.ASCII: \w == [A-Za-z0-9_], \s == [ \t\n\r\f\v]. Match those explicitly so JS \w/\s
// (which differ on unicode) cannot drift.
const _NON_WORD = /[^A-Za-z0-9_ \t\n\r\f\v]/g
const _WS = /[ \t\n\r\f\v]+/g
function normalizeTitle(title) {
  let t = String(title).toLowerCase()
  t = t.replace(_NON_WORD, '')
  t = t.replace(_WS, ' ')
  return t.trim()
}
function findingIdentity(finding) {
  return `${(finding && finding.file) || ''}::${normalizeTitle((finding && finding.title) || '')}`
}
function _blocking(round) { return round.findings.filter((f) => BLOCKING.has(f.severity)) }
function checkCircuitBreaker(rounds, maxRounds) {
  const n = rounds.length
  if (n === 0) return { halt: false, reason: null, detail: 'no rounds yet' }
  const latest = _blocking(rounds[n - 1])
  if (n >= maxRounds && latest.length > 0) {
    return { halt: true, reason: 'max-iterations',
      detail: `Reached ${maxRounds} rounds; the latest review still showed ${latest.length} blocking finding(s) (the final round's fixes are committed but not yet re-reviewed).` }
  }
  if (n >= 2) {
    const prevIds = new Set(_blocking(rounds[n - 2]).map(findingIdentity))
    const recurring = latest.filter((f) => prevIds.has(findingIdentity(f)))
    if (recurring.length) {
      const ids = recurring.map(findingIdentity).join('; ')
      return { halt: true, reason: 'recurring-finding',
        detail: `${recurring.length} blocking finding(s) recurred after a fix was committed: ${ids}` }
    }
  }
  if (n >= 3) {
    const cN = _blocking(rounds[n - 1]).length
    const cN1 = _blocking(rounds[n - 2]).length
    const cN2 = _blocking(rounds[n - 3]).length
    if (cN > 0 && cN >= cN1 && cN1 >= cN2) {
      return { halt: true, reason: 'no-net-progress',
        detail: `Blocking-finding count did not decrease over two rounds (${cN2} → ${cN1} → ${cN}).` }
    }
  }
  return { halt: false, reason: null, detail: 'progressing' }
}
module.exports = { normalizeTitle, findingIdentity, checkCircuitBreaker, BLOCKING }
