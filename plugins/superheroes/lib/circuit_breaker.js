// plugins/superheroes/lib/circuit_breaker.js
const { clampTitle, canonicalClassKey, classKeyAliases } = require('./review_memory.js')
const BLOCKING = new Set(['Critical', 'Important'])
// The ONLY severities that demote a finding to non-blocking: the rubric's non-blocking tiers
// (Minor/Nit — SSOT §11, guarded by test_ssot_drift). `isBlocking` is the single, case-normalized,
// FAIL-CLOSED blocking predicate every severity consumer routes through (#276): a foreign scale
// (`blocker`/`high`/`medium`), an unknown tier, a mis-cased `critical`, or a missing severity is
// treated as blocking — an unrecognized severity means blocking, never a silent demotion. Consumers
// keep BLOCKING for rank/identity/"was-tagged-blocking" bookkeeping but ask `isBlocking` the
// partition question, so _partition, the breaker's own stuck-detection, the panel gate, and the
// build legs can never disagree on what blocks.
const _NON_BLOCKING = new Set(['minor', 'nit'])
function isBlocking(severity) {
  return !_NON_BLOCKING.has(String(severity == null ? '' : severity).trim().toLowerCase())
}
// #291: the TIER-specific Critical match (case-normalized), single-sourced alongside isBlocking so the
// confirmation re-arm/park gate can't miss a mis-cased `critical`. Distinct from isBlocking: Important
// is blocking but NOT critical.
function isCritical(severity) {
  return String(severity == null ? '' : severity).trim().toLowerCase() === 'critical'
}
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
function findingLabel(finding) {
  if (!finding || typeof finding !== 'object') return ''
  return finding.title || finding.summary || ''
}
function findingIdentity(finding) {
  return `${(finding && finding.file) || ''}::${normalizeTitle(clampTitle(findingLabel(finding)))}`
}
function recurrenceKey(finding) {
  if (finding && (finding.dimension || finding.taxonomy)) return canonicalClassKey(finding)
  if (finding && finding.classKey) return finding.classKey
  return findingIdentity(finding)
}
function recurrenceAliases(finding) {
  const aliases = new Set([recurrenceKey(finding)])
  if (finding && (finding.dimension || finding.taxonomy)) {
    for (const alias of classKeyAliases(finding)) aliases.add(alias)
  }
  return aliases
}
function intersects(a, b) {
  for (const x of a) if (b.has(x)) return true
  return false
}
function _blocking(round) { return round.findings.filter((f) => isBlocking(f.severity)) }
function _roundRecordedFix(roundRec) {
  // Parity twin of circuit_breaker._round_recorded_fix: true when this round's fixer recorded
  // applied fixes (rec.fix.fixes). The cap-halt precedes the round's fix leg, so the latest round
  // usually carries no fix — keeps the max-iterations detail honest instead of always claiming one.
  const fix = roundRec && roundRec.fix
  if (!fix || typeof fix !== 'object') return false
  const fixes = fix.fixes
  return Array.isArray(fixes) ? fixes.length > 0 : !!fixes
}
function _generalizeKeys(roundRec) {
  return new Set((roundRec.generalizeRequired || []).filter((g) => g && g.classKey).map((g) => g.classKey))
}
function _blockingCountExcludingGeneralize(roundRec) {
  const generalize = _generalizeKeys(roundRec)
  const blocking = _blocking(roundRec)
  if (!generalize.size) return blocking.length
  return blocking.filter((f) => !intersects(recurrenceAliases(f), generalize)).length
}
function _roundReviewed(roundRec) {
  const dims = roundRec && roundRec.dimensions
  if (!dims || typeof dims !== 'object' || Array.isArray(dims)) return true
  const entries = Object.values(dims)
  if (!entries.length) return true
  return entries.some((d) => d && d.status === 'run')
}
function _reviewedRounds(rounds) {
  return (rounds || []).filter(_roundReviewed)
}
function checkCircuitBreaker(rounds, maxRounds) {
  const n = rounds.length
  if (n === 0) return { halt: false, reason: null, detail: 'no rounds yet' }
  const latest = _blocking(rounds[n - 1])
  if (n >= maxRounds && latest.length > 0) {
    // Honest halt detail (#212 class): name the ACTUAL round reached (n) alongside the cap — a resume
    // can run past the cap, so n may exceed maxRounds — and only claim "fixes committed" when the final
    // round actually recorded a fix. The cap-halt fires right after a review and before that round's
    // fixer runs, so the latest round usually carries no fix; saying otherwise misreads a park that
    // needs a fix-then-relaunch as one that only needs a re-review.
    const tail = _roundRecordedFix(rounds[n - 1])
      ? "the final round's fixes are committed but not yet re-reviewed"
      : 'no fix was applied this round — the finding(s) remain unaddressed'
    // Don't overstate how many REAL reviews ran: n counts every recorded round (the gate uses it),
    // but a transport-failed / all-missing round inflates it. When fewer rounds were actually reviewed
    // than recorded, say so (same honesty _reviewedRounds gives criteria 1-2).
    let capNote = `cap ${maxRounds}`
    const reviewedN = _reviewedRounds(rounds).length
    if (reviewedN < n) capNote += `, ${reviewedN} reviewed`
    return { halt: true, reason: 'max-iterations',
      detail: `Reached round ${n} (${capNote}); the latest review still showed ${latest.length} blocking finding(s) (${tail}).` }
  }
  const reviewed = _reviewedRounds(rounds)
  const rn = reviewed.length
  if (rn >= 3) {
    const cN = _blockingCountExcludingGeneralize(reviewed[rn - 1])
    const cN1 = _blockingCountExcludingGeneralize(reviewed[rn - 2])
    const cN2 = _blockingCountExcludingGeneralize(reviewed[rn - 3])
    if (cN > 0 && cN >= cN1 && cN1 >= cN2) {
      return { halt: true, reason: 'no-net-progress',
        detail: `Blocking-finding count did not decrease over two rounds (${cN2} → ${cN1} → ${cN}).` }
    }
  }
  if (rn >= 2) {
    const latestRec = reviewed[rn - 1]
    const latestGeneralize = new Set((latestRec.generalizeRequired || []).filter((g) => g && g.classKey).map((g) => g.classKey))
    const challenged = new Set((latestRec.coverageDecisions || []).filter((d) => d && d.classKey && d.challengedBy).map((d) => d.classKey))
    const latestBlocking = _blocking(latestRec)
    const prevIds = new Set()
    for (const f of _blocking(reviewed[rn - 2])) for (const alias of recurrenceAliases(f)) prevIds.add(alias)
    const recurring = latestBlocking.filter((f) => intersects(recurrenceAliases(f), prevIds))
    const challengedRecurring = recurring.filter((f) => intersects(recurrenceAliases(f), challenged))
    if (challengedRecurring.length) {
      const ids = challengedRecurring.map(recurrenceKey).join('; ')
      return { halt: true, reason: 'challenged-principle-recurring',
        detail: `${challengedRecurring.length} challenged coverage decision class recurred after being recorded: ${ids}` }
    }
    if (recurring.length) {
      const keys = new Set(recurring.map(recurrenceKey))
      for (const k of keys) {
        if (latestGeneralize.has(k)) {
          return { halt: false, reason: null, detail: 'recurrence pending coverage decision' }
        }
      }
      const ids = Array.from(keys).sort().join('; ')
      return { halt: true, reason: 'recurring-finding',
        detail: `${recurring.length} blocking finding(s) recurred after a fix was committed: ${ids}` }
    }
  }
  return { halt: false, reason: null, detail: 'progressing' }
}
module.exports = { normalizeTitle, findingIdentity, recurrenceKey, recurrenceAliases, checkCircuitBreaker, BLOCKING, isBlocking, isCritical }
