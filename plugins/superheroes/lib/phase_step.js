// plugins/superheroes/lib/phase_step.js
// Faithful JS twin of phase_step.py:decide — parity-locked. Safety ordering: assumption /
// low-confidence parks are evaluated BEFORE the gate (a recorded assumption parks even on a
// passed gate). Pure + fail-closed.
function pyReprStr(v) {
  // Python %r for a simple str: single-quoted, backslash- and quote-escaped.
  if (typeof v === 'string') return "'" + v.replace(/\\/g, '\\\\').replace(/'/g, "\\'") + "'"
  if (v === null || v === undefined) return 'None'
  return String(v)
}
function decide(phaseResult, gate) {
  const pr = phaseResult || {}
  if (pr.assumptions && pr.assumptions.length) {
    // #212: name WHICH assumption(s) — the payload carries the list. The infra parkReason override
    // still wins at the consumer; this richer reason surfaces where no override was set.
    const detail = pr.assumptions.map((a) => String(a)).join('; ')
    let reason = 'phase recorded a material assumption'
    if (detail) reason += ': ' + detail
    return { action: 'park_assumption', reason }
  }
  if (pr.confidence === 'low') {
    return { action: 'park_low_confidence', reason: 'phase recorded confidence below the parking threshold' }
  }
  if (gate === null || gate === undefined || gate === 'passed') {
    return { action: 'proceed', reason: (gate === null || gate === undefined) ? 'no review gate' : 'gate passed' }
  }
  if (gate === 'changes-requested') {
    // #212: thread the named terminal reason (parkDetail) so the workflow park survives the flatten.
    let reason = 'review requested changes'
    if (pr.parkDetail) reason += ' — ' + String(pr.parkDetail)
    return { action: 'park_changes_requested', reason }
  }
  if (gate === 'pending') return { action: 'park_pending', reason: 'gate not passed (pending / not yet approved)' }
  return { action: 'park_unexpected_gate', reason: 'unexpected or unreadable gate value: ' + pyReprStr(gate) }
}
module.exports = { decide }
