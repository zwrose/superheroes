// plugins/superheroes/lib/test_pilot_phase.js
// Native showrunner test-pilot phase. This module stays dependency-injected so the
// showrunner spine can be smoke-tested without launching browsers or mutating refs.

async function testPilotPhase(workItem, generation, deps) {
  deps = deps || {}
  const assumptions = []

  let context
  try {
    context = await callLeaf(deps.resolveContext, workItem, generation)
  } catch (err) {
    return low(`test-pilot setup failed: ${message(err)}`)
  }
  if (!context || !context.head) {
    return low('test-pilot setup failed: missing current head')
  }

  let applicability
  try {
    applicability = await callLeaf(deps.decideApplicability, context)
  } catch (err) {
    return low(`test-pilot applicability failed: ${message(err)}`)
  }
  if (!applicability || typeof applicability !== 'object') {
    return low('test-pilot applicability failed: no verdict')
  }

  if (applicability.verdict === 'not_applicable') {
    const status = {
      schemaVersion: 1,
      verdict: 'not_applicable',
      workItem,
      branch: context.branch,
      head: context.head,
      rationale: applicability.rationale || applicability.reason || 'no browser-verifiable workflow changed',
    }
    const wrote = await writeStatus(deps, workItem, status)
    if (!wrote.ok) return low(wrote.reason)
    return { confidence: 'high', assumptions }
  }

  if (applicability.verdict !== 'applicable') {
    return low(applicability.reason || 'test-pilot applicability is uncertain')
  }

  if (!context.profile) {
    return low('test-pilot setup missing calibration/profile')
  }
  if (!context.browserTool) {
    return low('test-pilot setup missing browser tool')
  }

  let plan
  try {
    plan = await callLeaf(deps.derivePlan, context)
  } catch (err) {
    return low(`test-pilot plan derivation failed: ${message(err)}`)
  }
  const records = plan && (plan.records || plan.planRecords)
  if (!Array.isArray(records) || records.length === 0) {
    return low('applicable test-pilot plan is empty')
  }

  return low('applicable test-pilot execution is not wired yet')
}

async function writeStatus(deps, workItem, status) {
  try {
    if (deps.writeStatus) {
      const out = await deps.writeStatus(status, workItem)
      if (out && out.ok === false) return { ok: false, reason: out.reason || 'test-pilot status write failed' }
      return { ok: true }
    }
  } catch (err) {
    return { ok: false, reason: `test-pilot status write failed: ${message(err)}` }
  }
  return { ok: false, reason: 'test-pilot status writer unavailable' }
}

async function callLeaf(fn, ...args) {
  if (typeof fn !== 'function') throw new Error('required leaf is unavailable')
  return fn(...args)
}

function low(reason) {
  return { confidence: 'low', assumptions: [reason] }
}

function message(err) {
  return err && err.message ? err.message : String(err || 'unknown')
}

module.exports = { testPilotPhase }
