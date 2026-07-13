// #397 FR-14: deterministic prefilter + consumer for accepted doc findings at re-review.
const { findingIdentity, isBlocking } = require('./circuit_breaker.js')
const loopSynthesis = require('./loop_synthesis.js')

function prefilterForJudge(merged, candidates) {
  const matchIds = new Set()
  for (const c of candidates || []) {
    if (c && c.hashMatches && c.identity) matchIds.add(c.identity)
  }
  const offered = []
  for (const f of merged || []) {
    const ident = findingIdentity(f)
    if (matchIds.has(ident)) offered.push(ident)
  }
  return offered
}

function splitVerdicts(leafVerdicts, offered) {
  const offeredSet = new Set(offered || [])
  const acceptance = []
  const normal = []
  if (!Array.isArray(leafVerdicts)) return { acceptance, normal }
  for (const v of leafVerdicts) {
    if (!v || typeof v !== 'object') continue
    if (offeredSet.has(v.id)) acceptance.push(v)
    else normal.push(v)
  }
  return { acceptance, normal }
}

function acceptanceDrops(merged, acceptanceVerdicts, offered) {
  const offeredSet = new Set(offered || [])
  const byId = Object.create(null)
  for (const v of acceptanceVerdicts || []) {
    if (v && typeof v.id === 'string') byId[v.id] = v
  }
  const drops = []
  const survivors = []
  for (const f of merged || []) {
    const ident = findingIdentity(f)
    if (!offeredSet.has(ident)) {
      survivors.push(f)
      continue
    }
    const v = byId[ident]
    const action = v && v.action
    const reason = v && v.reason
    if (action === 'same' && typeof reason === 'string' && reason.trim()) {
      drops.push({
        id: ident,
        file: f.file === undefined ? null : f.file,
        title: f.title === undefined ? null : f.title,
        reason: reason.trim(),
        was_blocking_tagged: isBlocking(f.severity),
        accepted: true,
      })
    } else {
      survivors.push(f)
    }
  }
  return { survivors, drops }
}

function consumeWithAcceptance(merged, leafVerdicts, candidates) {
  const offered = prefilterForJudge(merged, candidates)
  const { acceptance, normal } = splitVerdicts(leafVerdicts, offered)
  const { survivors, drops: accDrops } = acceptanceDrops(merged, acceptance, offered)
  const normalOut = loopSynthesis.consume(survivors, normal)
  return {
    findings: normalOut.findings || [],
    drops: accDrops.concat(normalOut.drops || []),
    downgrades: normalOut.downgrades || [],
  }
}

module.exports = {
  prefilterForJudge,
  consumeWithAcceptance,
}
