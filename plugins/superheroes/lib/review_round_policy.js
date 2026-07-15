// plugins/superheroes/lib/review_round_policy.js
const { isCritical, isBlocking } = require('./circuit_breaker.js')
const DEEP = 'reviewer-deep'
const CHEAP = 'reviewer'
// #174 confirmation-bar economics: at most this many FULL confirmation panels per loop, and the
// rework-breadth (distinct policy subjects the fix touched) at or above which a confirmation's
// rework counts as "cross-cutting" and re-arms one more full confirmation.
const MAX_CONFIRMATIONS = 2
const CROSS_CUTTING_SUBJECTS = 3
const SUBJECT_FALLBACK = {
  test: 'Test',
  security: 'Security',
  code: 'Code',
  architecture: 'Architecture',
  failure: 'Failure-Mode',
  premortem: 'Failure-Mode',
}
const POLICY_SUBJECTS = new Set(Object.values(SUBJECT_FALLBACK))

function _dim(prev, name) {
  if (!prev || typeof prev !== 'object' || Array.isArray(prev)) return {}
  const info = prev[name]
  return info && typeof info === 'object' && !Array.isArray(info) ? info : {}
}

function _changedSubjects(value) {
  if (!Array.isArray(value)) return null
  const out = []
  for (const item of value) {
    if (typeof item === 'string') {
      out.push(item)
      continue
    }
    if (item && typeof item === 'object' && !Array.isArray(item)) {
      for (const key of ['subject', 'dimension', 'policySubject']) {
        const subject = _policySubject(item[key])
        if (subject) out.push(subject)
      }
      // Section-only doc-reviser notes intentionally map to "known empty": cheap skips are bounded by the mandatory deep confirmation round.
      continue
    }
    return null
  }
  return Array.from(new Set(out))
}

function _policySubject(value) {
  if (typeof value !== 'string' || !value) return null
  if (POLICY_SUBJECTS.has(value)) return value
  return SUBJECT_FALLBACK[String(value || '').split('-')[0].toLowerCase()] || null
}

function _safeRound(value) {
  if (value === null || value === undefined || value === '') return { value: 1, malformed: false }
  if (typeof value === 'string' && value.includes('.')) return { value: 1, malformed: true }
  const n = Number(value)
  if (!Number.isFinite(n) || !Number.isInteger(n)) return { value: 1, malformed: true }
  return { value: n, malformed: false }
}

function _subjects(name, info) {
  if (Array.isArray(info.subjects)) return info.subjects.filter((s) => typeof s === 'string')
  const subjects = []
  for (const finding of Array.isArray(info.findings) ? info.findings : []) {
    if (finding && typeof finding.dimension === 'string') subjects.push(finding.dimension)
  }
  const fallback = SUBJECT_FALLBACK[String(name || '').split('-')[0].toLowerCase()]
  if (fallback) subjects.push(fallback)
  return Array.from(new Set(subjects))
}

function _hasFindings(info) {
  for (const value of [info.findings, info.currentFindings, info.carriedFindings]) {
    if (Array.isArray(value) && value.length > 0) return true
  }
  if (typeof info.hasFindings === 'boolean') return info.hasFindings
  if (Array.isArray(info.findings)) return info.findings.length > 0
  return null
}

function _subjectTouched(name, info, changedSubjects) {
  if (changedSubjects === null || changedSubjects === undefined) return null
  const subjects = _subjects(name, info)
  return subjects.some((s) => changedSubjects.includes(s))
}

function planRound(state) {
  state = state || {}
  const dimensions = Array.isArray(state.dimensions) ? state.dimensions : []
  const previous = state.previous && typeof state.previous === 'object' && !Array.isArray(state.previous) ? state.previous : {}
  const changedSubjects = _changedSubjects(state.changedSubjects)
  const parsedRound = _safeRound(state.round)
  const roundNo = parsedRound.value

  if (parsedRound.malformed) {
    const out = {}
    for (const d of dimensions) out[d] = { action: 'run', tier: DEEP, reason: 'malformed round state' }
    return { roundKind: 'intermediate', dimensions: out, escalationPolicy: 'deep-only' }
  }

  if (state.confirmation) {
    const out = {}
    for (const d of dimensions) out[d] = { action: 'run', tier: DEEP, reason: 'confirmation full-panel' }
    return { roundKind: 'confirmation', dimensions: out, escalationPolicy: 'deep-only' }
  }
  if (roundNo <= 1) {
    const out = {}
    for (const d of dimensions) out[d] = { action: 'run', tier: DEEP, reason: 'baseline full-panel' }
    return { roundKind: 'baseline', dimensions: out, escalationPolicy: 'deep-only' }
  }
  if (changedSubjects === null || changedSubjects === undefined) {
    const out = {}
    for (const d of dimensions) out[d] = { action: 'run', tier: DEEP, reason: 'unknown changed subjects' }
    return { roundKind: 'intermediate', dimensions: out, escalationPolicy: 'deep-only' }
  }

  const out = {}
  for (const name of dimensions) {
    const info = _dim(previous, name)
    const touched = _subjectTouched(name, info, changedSubjects)
    const hasFindings = _hasFindings(info)
    if (hasFindings === true || touched) {
      out[name] = { action: 'run', tier: CHEAP, reason: 'previous finding or changed subject' }
    } else if (info.confidence === 'high' && hasFindings === false) {
      out[name] = { action: 'skip', tier: DEEP, reason: 'high-confidence clean and untouched', carriedFromRound: info.round }
    } else {
      out[name] = { action: 'run', tier: DEEP, reason: 'not skip eligible' }
    }
  }
  return { roundKind: 'intermediate', dimensions: out, escalationPolicy: 'cheap-first' }
}

function isCrossCutting(changedSubjects, threshold = CROSS_CUTTING_SUBJECTS) {
  // #174: the rework of a confirmation's fix is "cross-cutting" when it touched at least
  // `threshold` distinct policy subjects (default ≥3 of the 5). Reuses the shared changed-subjects
  // normalizer, so a malformed / unknown surface returns null → treated as cross-cutting (fail
  // toward one more confirmation, never toward a premature certify).
  const subjects = _changedSubjects(changedSubjects)
  if (subjects === null || subjects === undefined) return true
  return new Set(subjects).size >= threshold
}

function confirmationFollowup(surfacedSeverities, confirmationsRun, crossCutting,
  maxConfirmations = MAX_CONFIRMATIONS, docMode = false) {
  // #174 confirmation-bar economics — the follow-up decision after a FULL confirmation panel
  // surfaced blocking findings (which the fix loop still resolves + verifies, requirement 1).
  // Only a Critical surfaced, OR cross-cutting rework, triggers one more full confirmation; hard
  // cap of `maxConfirmations` panels; a Critical still owed at the cap parks (certification
  // withheld), a non-Critical at the cap is resolved by a scoped verify then certified.
  const sevs = (surfacedSeverities || []).filter((s) => typeof s === 'string')
  const atCap = confirmationsRun >= maxConfirmations
  if (docMode) {
    const hasBlocking = sevs.some((s) => isBlocking(s))
    if (!hasBlocking) {
      return { rearm: false, park: false, atCap,
        reason: 'no open blocking finding — doc review certifies' }
    }
    if (atCap) {
      return { rearm: false, park: true, atCap: true,
        reason: 'open blocking finding at the doc-review round cap — park; certification withheld' }
    }
    return { rearm: true, park: false, atCap: false,
      reason: 'open blocking finding in doc review — one more full confirmation panel required' }
  }
  // #291: case-normalized Critical match — a surfaced mis-cased `critical` must still park at the cap
  // (was `sevs.includes('Critical')`, case-sensitive, so a lowercase Critical resolved by scoped verify).
  const hasCritical = sevs.some((s) => isCritical(s))
  const trigger = hasCritical || !!crossCutting
  if (!trigger) {
    return { rearm: false, park: false, atCap,
      reason: 'non-Critical findings, rework not cross-cutting — resolve by scoped verify; no further confirmation panel' }
  }
  if (atCap) {
    if (hasCritical) {
      return { rearm: false, park: true, atCap: true,
        reason: 'Critical surfaced at the confirmation-panel cap — park; certification withheld' }
    }
    return { rearm: false, park: false, atCap: true,
      reason: 'confirmation-panel cap reached — resolve remaining by scoped verify; no further panel' }
  }
  return { rearm: true, park: false, atCap: false,
    reason: (hasCritical ? 'Critical surfaced by confirmation' : 'cross-cutting rework') + ' — one more full confirmation panel required' }
}

module.exports = { planRound, isCrossCutting, confirmationFollowup, MAX_CONFIRMATIONS, CROSS_CUTTING_SUBJECTS }
