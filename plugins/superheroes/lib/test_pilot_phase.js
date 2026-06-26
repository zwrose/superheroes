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

  const setupProblem = validateSetup(context)
  if (setupProblem) {
    return low(setupProblem)
  }

  const previousStatus = await readPreviousStatus(deps, workItem)

  let plan
  try {
    plan = await callLeaf(deps.derivePlan, context)
  } catch (err) {
    return low(`test-pilot plan derivation failed: ${message(err)}`)
  }
  if (plan && plan.confidence === 'low') {
    return low(plan.reason || 'test-pilot plan derivation is low-confidence')
  }
  plan = normalizePlan(plan)
  if (!plan.records.length) {
    return low('applicable test-pilot plan is empty')
  }
  const generatedStoreProblem = generatedInRepoStoreProblem(plan.records)
  if (generatedStoreProblem) {
    return low(generatedStoreProblem)
  }
  const mergedRecords = mergePriorStepState(plan.records, previousStatus)
  const skippedProblem = validateSkippedPreservation(mergedRecords)
  if (skippedProblem) {
    return low(skippedProblem)
  }
  const dedupeProblem = validateUniqueIds(mergedRecords)
  if (dedupeProblem) {
    return low(dedupeProblem)
  }
  plan.records = mergedRecords
  let wrote = await writeStatus(deps, workItem, milestoneStatus(context, workItem, 'plan-derived', {
    planRecords: plan.records,
  }))
  if (!wrote.ok) return low(wrote.reason)

  let prepared
  try {
    prepared = await callLeaf(deps.preparePlanRecords, plan, context, previousStatus)
  } catch (err) {
    return low(`test-pilot plan record preparation failed: ${message(err)}`)
  }
  const recordProblem = planRecordProblem(prepared)
  if (recordProblem) {
    return low(recordProblem)
  }
  const records = mergePriorStepState(prepared.records, previousStatus)
  const preparedSkippedProblem = validateSkippedPreservation(records)
  if (preparedSkippedProblem) {
    return low(preparedSkippedProblem)
  }
  const preparedDedupeProblem = validateUniqueIds(records)
  if (preparedDedupeProblem) {
    return low(preparedDedupeProblem)
  }
  wrote = await writeStatus(deps, workItem, milestoneStatus(context, workItem, 'plan-records-ready', {
    planRecords: records,
  }))
  if (!wrote.ok) return low(wrote.reason)

  let artifactResult
  try {
    artifactResult = await callLeaf(deps.prepareArtifacts, {
      plan: Object.assign({}, plan, { records }),
      records,
      context,
      previousStatus,
    })
  } catch (err) {
    return low(`test-pilot artifact preparation failed: ${message(err)}`)
  }
  const artifactProblem = artifactReadinessProblem(artifactResult)
  if (artifactProblem) {
    return low(artifactProblem)
  }
  wrote = await writeStatus(deps, workItem, milestoneStatus(context, workItem, 'artifacts-ready', {
    planRecords: records,
    artifacts: artifactResult.artifacts,
    prPosting: artifactResult.posting || artifactResult.prPosting,
    fallback: artifactResult.fallback,
  }))
  if (!wrote.ok) return low(wrote.reason)

  let serverContext
  try {
    serverContext = await callLeaf(deps.resolveServer, context, records)
  } catch (err) {
    return low(`test-pilot server resolution failed: ${message(err)}`)
  }
  const serverProblem = serverContextProblem(serverContext, context)
  if (serverProblem) {
    return low(serverProblem)
  }
  wrote = await writeStatus(deps, workItem, milestoneStatus(context, workItem, 'server-ready', {
    planRecords: records,
    artifacts: artifactResult.artifacts,
    server: publicServerContext(serverContext),
  }))
  if (!wrote.ok) return low(wrote.reason)

  let seedResult
  try {
    seedResult = await callLeaf(deps.seedRecords, records, context)
  } catch (err) {
    return low(`test-pilot seed preparation failed: ${message(err)}`)
  }
  const seedProblem = seedReadinessProblem(seedResult)
  if (seedProblem) {
    return low(seedProblem)
  }
  wrote = await writeStatus(deps, workItem, milestoneStatus(context, workItem, 'seed-ready', {
    planRecords: records,
    artifacts: artifactResult.artifacts,
    server: publicServerContext(serverContext),
    seed: seedResult.status || seedResult,
  }))
  if (!wrote.ok) return low(wrote.reason)

  let rawResults
  try {
    rawResults = await runWithServer(deps, serverContext, async (activeServer) => {
      const browserContext = browserLeafContext(context, activeServer, records, artifactResult, seedResult)
      return callLeaf(deps.runBrowserPass, browserContext)
    })
  } catch (err) {
    return low(`test-pilot browser execution failed: ${message(err)}`)
  }
  const originProblem = browserOriginProblem(rawResults, serverContext)
  if (originProblem) {
    return low(originProblem)
  }

  let aggregated
  try {
    aggregated = await callLeaf(deps.aggregateResults, rawResults, {
      context,
      records,
      server: serverContext,
    })
  } catch (err) {
    return low(`test-pilot result aggregation failed: ${message(err)}`)
  }
  const evidenceProblem = resultEvidenceProblem(aggregated, records)
  if (evidenceProblem) {
    return low(evidenceProblem)
  }

  const finalStatus = {
    schemaVersion: 1,
    verdict: 'applicable',
    workItem,
    branch: context.branch,
    head: context.head,
    records: mergeAllowedSkippedResults(aggregated.records, records),
    artifacts: artifactResult.artifacts,
    prPosting: artifactResult.posting || artifactResult.prPosting,
    baseline: context.baseline || { head: context.head },
    review: context.review || { head: context.head },
    remotePr: context.remotePr || context.remotePR || { head: context.head },
  }
  if (aggregated.coverageRationale || plan.coverageRationale) {
    finalStatus.coverageRationale = aggregated.coverageRationale || plan.coverageRationale
  }
  if (aggregated.fixes) finalStatus.fixes = aggregated.fixes
  if (aggregated.verify) finalStatus.verify = aggregated.verify
  wrote = await writeStatus(deps, workItem, finalStatus)
  if (!wrote.ok) return low(wrote.reason)

  return { confidence: 'high', assumptions }
}

function validateSetup(context) {
  if (!context.profile) {
    return 'test-pilot setup missing calibration/profile'
  }
  if (!context.browserTool) {
    return 'test-pilot setup missing browser tool'
  }
  const baseUrl = context.baseUrl || (context.profile && (context.profile.baseUrl || context.profile.base_url))
  if (!baseUrl) {
    return 'test-pilot setup missing baseUrl'
  }
  const allowed = context.allowedOrigins || context.allowed_origins || (context.profile && (context.profile.allowedOrigins || context.profile.allowed_origins))
  if (!Array.isArray(allowed) || allowed.length === 0) {
    return 'test-pilot setup missing allowedOrigins'
  }
  return null
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

async function readPreviousStatus(deps, workItem) {
  if (typeof deps.readStatus !== 'function') return null
  try {
    const out = await deps.readStatus(workItem)
    return out && typeof out === 'object' ? out : null
  } catch (_) {
    return null
  }
}

function normalizePlan(plan) {
  const source = plan && typeof plan === 'object' ? plan : {}
  const records = source.records || source.planRecords
  return Object.assign({}, source, { records: Array.isArray(records) ? records : [] })
}

function generatedInRepoStoreProblem(records) {
  for (const record of records) {
    const store = record && (record.store || record.planStore || record.generatedStore)
    const location = store && (store.location || store.mode)
    const generated = (store && store.generated === true) || record.generated === true || record.generatedManifest === true
    if (generated && (location === 'in_repo' || location === 'in-repo')) {
      return 'generated in-repo plan store writes must park before touching worktree'
    }
  }
  return null
}

function previousRecords(status) {
  return status && Array.isArray(status.records) ? status.records : []
}

function stepKey(value) {
  if (!value || typeof value !== 'object') return null
  const raw = value.id || value.stepId || value.step_id
  return raw == null || raw === '' ? null : String(raw)
}

function mergePriorStepState(records, previousStatus) {
  const prior = new Map()
  for (const record of previousRecords(previousStatus)) {
    const key = stepKey(record)
    if (key) prior.set(key, record)
  }
  return records.map((record) => {
    if (!record || typeof record !== 'object') return record
    const seen = new Set()
    const steps = []
    for (const step of Array.isArray(record.steps) ? record.steps : []) {
      if (!step || typeof step !== 'object') continue
      const key = stepKey(step)
      if (key && seen.has(key)) continue
      if (key) seen.add(key)
      const merged = Object.assign({}, step)
      const old = key ? prior.get(key) : null
      if (old) {
        for (const field of ['checked', 'checkboxState', 'humanChecked', 'humanCheckboxState']) {
          if (old[field] !== undefined && merged[field] === undefined) merged[field] = old[field]
        }
        if (merged.priorResult === undefined) merged.priorResult = old.result || old.status
      }
      if (Array.isArray(merged.scenarioIds)) {
        merged.scenarioIds = [...new Set(merged.scenarioIds.map(String).filter(Boolean))]
      }
      steps.push(merged)
    }
    return Object.assign({}, record, { steps })
  })
}

function validateSkippedPreservation(records) {
  for (const record of records) {
    for (const step of (record && Array.isArray(record.steps) ? record.steps : [])) {
      const skipped = step.status === 'skipped' || step.result === 'skipped' || step.skipped === true
      if (!skipped) continue
      if (!stepKey(step) || !step.removalReason || !step.priorResult || !step.planContext) {
        return 'skipped step preservation missing step id, removal reason, prior result, or updated plan context'
      }
    }
  }
  return null
}

function validateUniqueIds(records) {
  const stepIds = new Set()
  const scenarioIds = new Set()
  for (const record of records) {
    if (!record || typeof record !== 'object') return 'malformed plan records'
    const steps = record.steps
    if (!Array.isArray(steps) || steps.length === 0) return 'malformed plan records: steps missing'
    for (const step of steps) {
      const key = stepKey(step)
      if (!key) return 'malformed plan records: step id missing'
      if (stepIds.has(key)) return `duplicate browser step id: ${key}`
      stepIds.add(key)
      for (const sid of Array.isArray(step.scenarioIds) ? step.scenarioIds : []) {
        const value = String(sid)
        if (scenarioIds.has(value)) continue
        scenarioIds.add(value)
      }
    }
  }
  return null
}

function planRecordProblem(prepared) {
  if (!prepared || typeof prepared !== 'object') return 'test-pilot plan record preparation returned no result'
  if (prepared.confidence === 'low') return prepared.reason || 'test-pilot plan record preparation is low-confidence'
  if (prepared.action === 'park' || prepared.ok === false) return prepared.reason || 'test-pilot plan records are invalid'
  if (!Array.isArray(prepared.records) || prepared.records.length === 0) return 'test-pilot plan records missing after preparation'
  return null
}

function artifactReadinessProblem(result) {
  if (!result || typeof result !== 'object') return 'test-pilot artifact preparation returned no result'
  if (result.confidence === 'low') return result.reason || 'test-pilot artifact preparation is low-confidence'
  if (result.action === 'park' || result.ok === false) return result.reason || 'test-pilot artifact preparation parked'
  if (!result.artifacts || !result.artifacts.plan) return 'plan artifact missing before seed/browser execution'
  return null
}

function seedReadinessProblem(result) {
  if (!result || typeof result !== 'object') return 'test-pilot seed preparation returned no result'
  if (result.confidence === 'low') return result.reason || 'test-pilot seed preparation is low-confidence'
  if (result.action === 'park' || result.ok === false) return result.reason || 'test-pilot seed preparation parked'
  if (!['ready_for_browser', 'verified', 'ready'].includes(result.action) && result.ready !== true) {
    return 'test-pilot seed state was not verified before browser execution'
  }
  return null
}

function serverContextProblem(server, context) {
  if (!server || typeof server !== 'object') return 'test-pilot server resolution returned no context'
  if (server.verdict === 'park' || server.action === 'park' || server.ok === false) return server.reason || 'test-pilot server resolution parked'
  if (!['ready_external', 'managed'].includes(server.verdict)) return 'test-pilot server resolution did not confirm external or managed server'
  if (!server.baseUrl) return 'test-pilot server resolution missing baseUrl'
  const allowed = server.allowedOrigins || server.allowed_origins || context.allowedOrigins || context.allowed_origins || (context.profile && context.profile.allowedOrigins)
  if (!Array.isArray(allowed) || !allowed.length) return 'test-pilot server resolution missing allowedOrigins'
  server.allowedOrigins = allowed
  if (server.verdict === 'managed') {
    if (!Array.isArray(server.command) || !server.command.length) return 'managed server command argv missing'
    if (server.shell !== false) return 'managed server must launch with shell=false'
  }
  return null
}

function publicServerContext(server) {
  const out = Object.assign({}, server)
  if (out.handle) out.handle = '[managed]'
  return out
}

async function runWithServer(deps, serverContext, run) {
  if (serverContext.verdict === 'managed') {
    return callLeaf(deps.withManagedServer, serverContext, run)
  }
  return run(serverContext)
}

function browserLeafContext(context, server, records, artifacts, seed) {
  return {
    workItem: context.workItem,
    branch: context.branch,
    head: context.head,
    profile: context.profile,
    browserTool: context.browserTool,
    baseUrl: server.baseUrl,
    allowedOrigins: server.allowedOrigins,
    server,
    records,
    artifacts,
    seed,
  }
}

function browserOriginProblem(rawResults, server) {
  const allowed = new Set((server.allowedOrigins || []).map(originOf).filter(Boolean))
  allowed.add(originOf(server.baseUrl))
  const urls = []
  collectUrls(rawResults, urls)
  for (const url of urls) {
    const origin = originOf(url)
    if (origin && !allowed.has(origin)) {
      return `off-origin browser navigation/result cannot count: ${bounded(url)}`
    }
  }
  const resultOrigin = originOf(rawResults && rawResults.baseUrl)
  if (resultOrigin && !allowed.has(resultOrigin)) {
    return `off-origin browser navigation/result cannot count: ${bounded(rawResults.baseUrl)}`
  }
  return null
}

function collectUrls(value, urls) {
  if (!value || typeof value !== 'object') return
  if (Array.isArray(value)) {
    value.forEach((entry) => collectUrls(entry, urls))
    return
  }
  for (const key of ['url', 'currentUrl', 'current_url', 'navigationUrl', 'navigation_url', 'baseUrl']) {
    if (typeof value[key] === 'string') urls.push(value[key])
  }
  for (const key of ['steps', 'records', 'navigations']) {
    collectUrls(value[key], urls)
  }
}

function originOf(url) {
  if (typeof url !== 'string' || !url) return null
  try {
    return new URL(url).origin
  } catch (_) {
    return null
  }
}

function bounded(value) {
  const text = String(value || '')
  return text.length > 200 ? `${text.slice(0, 197)}...` : text
}

function resultEvidenceProblem(aggregated, records) {
  if (!aggregated || typeof aggregated !== 'object') return 'test-pilot result aggregation returned no result'
  if (aggregated.confidence === 'low') return aggregated.reason || 'test-pilot result aggregation is low-confidence'
  if (aggregated.action === 'park' || aggregated.ok === false) return aggregated.reason || 'test-pilot result aggregation parked'
  if (!Array.isArray(aggregated.records) || aggregated.records.length === 0) return 'no browser-executed records were produced'
  const expected = new Set()
  for (const record of records) {
    for (const step of record.steps || []) {
      const key = stepKey(step)
      if (key && !(step.status === 'skipped' || step.result === 'skipped')) expected.add(key)
    }
  }
  const seen = new Set()
  for (const record of aggregated.records) {
    const key = stepKey(record)
    if (!key) return 'browser-derived pass/fail evidence missing step id'
    const status = record.status || record.result
    if (status !== 'passed' && status !== 'pass') return 'skipped, incomplete, or failing browser records park before readiness'
    if (record.browserExecuted !== true && record.browser_executed !== true && record.kind !== 'browser' && record.type !== 'browser') {
      return 'every browser step must have browser-derived pass/fail evidence'
    }
    seen.add(key)
  }
  for (const key of expected) {
    if (!seen.has(key)) return `browser-derived pass/fail evidence missing for step ${key}`
  }
  return null
}

function mergeAllowedSkippedResults(resultRecords, planRecords) {
  const records = resultRecords.map((record) => Object.assign({}, record))
  for (const planRecord of planRecords) {
    for (const step of planRecord.steps || []) {
      const skipped = step.status === 'skipped' || step.result === 'skipped'
      if (!skipped) continue
      records.push({
        stepId: stepKey(step),
        status: 'skipped',
        allowed: true,
        preserved: true,
        removalReason: step.removalReason,
        priorResult: step.priorResult,
        planContext: step.planContext,
        browserExecuted: true,
      })
    }
  }
  return records
}

function milestoneStatus(context, workItem, milestone, extra) {
  return Object.assign({
    schemaVersion: 1,
    verdict: 'park',
    milestone,
    workItem,
    branch: context.branch,
    head: context.head,
  }, extra || {})
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
