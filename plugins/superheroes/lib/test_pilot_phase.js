// plugins/superheroes/lib/test_pilot_phase.js
// Native showrunner test-pilot phase. This module stays dependency-injected so the
// showrunner spine can be smoke-tested without launching browsers or mutating refs.

// Native showrunner test-pilot phase. The orchestrator threads state through five sequential
// helpers, each of which returns `{ done: <terminalResult> }` to short-circuit (park or proceed) or
// the state it produced. Judgment stays in the injected leaves + pure helpers (§10.1); these helpers
// are control flow only.
const deciders = require('./test_pilot_deciders.js')

async function testPilotPhase(workItem, generation, deps) {
  deps = deps || {}

  const setup = await resolveApplicabilityAndSetup(deps, workItem, generation)
  if (setup.done) return setup.done
  const { context } = setup

  const planned = await preparePlanAndRecords(deps, workItem, context)
  if (planned.done) return planned.done
  const { plan, records, previousStatus } = planned

  const execCtx = await prepareExecutionContext(deps, workItem, context, plan, records, previousStatus)
  if (execCtx.done) return execCtx.done
  const { artifactResult, serverContext, seedResult } = execCtx

  const browser = await runBrowserPasses(deps, workItem, context, plan, records, artifactResult, serverContext, seedResult)
  if (browser.done) return browser.done
  const { combinedAggregated, retryState } = browser

  return finalizeReadiness(deps, workItem, context, plan, records, retryState, combinedAggregated, artifactResult)
}

// Phase 1: resolve context, decide applicability (short-circuit not_applicable / park uncertain),
// validate setup. Returns `{ context }` to proceed or `{ done }` for a terminal.
async function resolveApplicabilityAndSetup(deps, workItem, generation) {
  let context
  try {
    context = await callLeaf(deps.resolveContext, workItem, generation)
  } catch (err) {
    return { done: low(`test-pilot setup failed: ${message(err)}`) }
  }
  if (!context || !context.head) {
    return { done: low('test-pilot setup failed: missing current head') }
  }

  let applicability
  try {
    applicability = deciders.applicabilityDecision(context.diff, context.detectors, context.profile, context.planResult)
  } catch (err) {
    return { done: low(`test-pilot applicability failed: ${message(err)}`) }
  }
  if (!applicability || typeof applicability !== 'object') {
    return { done: low('test-pilot applicability failed: no verdict') }
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
    if (!wrote.ok) return { done: low(wrote.reason) }
    return { done: { confidence: 'high', assumptions: [] } }
  }

  if (applicability.verdict !== 'applicable') {
    return { done: low(applicability.reason || 'test-pilot applicability is uncertain') }
  }

  const setupProblem = validateSetup(context)
  if (setupProblem) {
    return { done: await parkLow(deps, workItem, context, setupProblem) }
  }

  return { context }
}

// Phase 2: derive the plan, prepare + validate plan records, write the plan milestones. Returns
// `{ plan, records, previousStatus }` to proceed or `{ done }` for a terminal.
async function preparePlanAndRecords(deps, workItem, context) {
  const previousStatus = await readPreviousStatus(deps, workItem)

  let plan
  try {
    plan = await callLeaf(deps.planTests || deps.derivePlan, context)
  } catch (err) {
    return { done: low(`test-pilot plan derivation failed: ${message(err)}`) }
  }
  if (plan && plan.confidence === 'low') {
    return { done: low(plan.reason || 'test-pilot plan derivation is low-confidence') }
  }
  plan = normalizePlan(plan)
  if (!plan.records.length) {
    return { done: await parkLow(deps, workItem, context, 'applicable test-pilot plan is empty') }
  }
  const generatedStoreProblem = generatedInRepoStoreProblem(plan.records)
  if (generatedStoreProblem) {
    return { done: await parkLow(deps, workItem, context, generatedStoreProblem) }
  }
  const mergedRecords = mergePriorStepState(plan.records, previousStatus)
  const skippedProblem = validateSkippedPreservation(mergedRecords)
  if (skippedProblem) {
    return { done: low(skippedProblem) }
  }
  const dedupeProblem = validateUniqueIds(mergedRecords)
  if (dedupeProblem) {
    return { done: low(dedupeProblem) }
  }
  plan.records = mergedRecords
  let wrote = await writeStatus(deps, workItem, milestoneStatus(context, workItem, 'plan-derived', {
    planRecords: plan.records,
  }))
  if (!wrote.ok) return { done: low(wrote.reason) }

  let prepared
  try {
    prepared = await callLeaf(deps.preparePlanRecords, plan, context, previousStatus)
  } catch (err) {
    return { done: low(`test-pilot plan record preparation failed: ${message(err)}`) }
  }
  const recordProblem = planRecordProblem(prepared)
  if (recordProblem) {
    return { done: await parkLow(deps, workItem, context, recordProblem) }
  }
  const records = mergePriorStepState(prepared.records, previousStatus)
  const preparedSkippedProblem = validateSkippedPreservation(records)
  if (preparedSkippedProblem) {
    return { done: low(preparedSkippedProblem) }
  }
  const preparedDedupeProblem = validateUniqueIds(records)
  if (preparedDedupeProblem) {
    return { done: low(preparedDedupeProblem) }
  }
  wrote = await writeStatus(deps, workItem, milestoneStatus(context, workItem, 'plan-records-ready', {
    planRecords: records,
  }))
  if (!wrote.ok) return { done: low(wrote.reason) }

  return { plan, records, previousStatus }
}

// Phase 3: prepare artifacts, resolve the server, seed records — each with its readiness milestone.
// Returns `{ artifactResult, serverContext, seedResult }` to proceed or `{ done }` for a terminal.
async function prepareExecutionContext(deps, workItem, context, plan, records, previousStatus) {
  if (typeof deps.prepareTestRun === 'function') {
    let folded
    try {
      folded = await callLeaf(deps.prepareTestRun, { plan, records, context, previousStatus, workItem })
    } catch (err) {
      return { done: low(`test-pilot preparation failed: ${message(err)}`) }
    }
    const artifactResult = folded && folded.artifactResult
    const serverContext = folded && folded.serverContext
    const seedResult = folded && folded.seedResult
    const artifactProblem = artifactReadinessProblem(artifactResult)
    if (artifactProblem) return { done: low(artifactProblem) }
    const serverProblem = serverContextProblem(serverContext, context)
    if (serverProblem) return { done: low(serverProblem) }
    const seedProblem = seedReadinessProblem(seedResult)
    if (seedProblem) return { done: low(seedProblem) }
    const wrote = await writeStatus(deps, workItem, milestoneStatus(context, workItem, 'seed-ready', {
      planRecords: records,
      artifacts: artifactResult.artifacts,
      server: publicServerContext(serverContext),
      seed: seedResult.status || seedResult,
    }))
    if (!wrote.ok) return { done: low(wrote.reason) }
    return { artifactResult, serverContext, seedResult }
  }

  let artifactResult
  try {
    artifactResult = await callLeaf(deps.prepareArtifacts, {
      plan: Object.assign({}, plan, { records }),
      records,
      context,
      previousStatus,
    })
  } catch (err) {
    return { done: low(`test-pilot artifact preparation failed: ${message(err)}`) }
  }
  const artifactProblem = artifactReadinessProblem(artifactResult)
  if (artifactProblem) {
    return { done: low(artifactProblem) }
  }
  let wrote = await writeStatus(deps, workItem, milestoneStatus(context, workItem, 'artifacts-ready', {
    planRecords: records,
    artifacts: artifactResult.artifacts,
    prPosting: artifactResult.posting || artifactResult.prPosting,
    fallback: artifactResult.fallback,
  }))
  if (!wrote.ok) return { done: low(wrote.reason) }

  let serverContext
  try {
    serverContext = await callLeaf(deps.resolveServer, context, records)
  } catch (err) {
    return { done: low(`test-pilot server resolution failed: ${message(err)}`) }
  }
  const serverProblem = serverContextProblem(serverContext, context)
  if (serverProblem) {
    return { done: low(serverProblem) }
  }
  wrote = await writeStatus(deps, workItem, milestoneStatus(context, workItem, 'server-ready', {
    planRecords: records,
    artifacts: artifactResult.artifacts,
    server: publicServerContext(serverContext),
  }))
  if (!wrote.ok) return { done: low(wrote.reason) }

  let seedResult
  try {
    seedResult = await callLeaf(deps.seedRecords, records, context)
  } catch (err) {
    return { done: low(`test-pilot seed preparation failed: ${message(err)}`) }
  }
  const seedProblem = seedReadinessProblem(seedResult)
  if (seedProblem) {
    return { done: low(seedProblem) }
  }
  wrote = await writeStatus(deps, workItem, milestoneStatus(context, workItem, 'seed-ready', {
    planRecords: records,
    artifacts: artifactResult.artifacts,
    server: publicServerContext(serverContext),
    seed: seedResult.status || seedResult,
  }))
  if (!wrote.ok) return { done: low(wrote.reason) }

  return { artifactResult, serverContext, seedResult }
}

// Phase 4: run browser passes, dispatch app-bug fix batches + review-code stabilization, until the
// evidence is clean (returns { combinedAggregated, retryState }) or a park condition returns { done }.
async function runBrowserPasses(deps, workItem, context, plan, records, artifactResult, serverContext, seedResult) {
  const retryState = {
    fixBatchHistory: [],
    currentHead: context.head,
    browserEvidenceHead: context.head,
    browserPasses: [],
    allRecords: records,
  }
  let aggregated
  let combinedAggregated = null
  let rerunScope = null
  let browserRecords = records
  let stabilizationCycle = 0
  while (true) {
    const budget = await budgetCheck(deps, 'browser-pass', {
      workItem,
      head: retryState.currentHead,
      rerunScope,
      fixBatchHistory: retryState.fixBatchHistory,
      counts: {
        browserPasses: retryState.browserPasses.length + 1,
        browserFixBatches: retryState.fixBatchHistory.length,
      },
    })
    if (!budget.ok) return { done: low(budget.reason) }

    let rawResults
    try {
      rawResults = await runWithServer(deps, serverContext, async (activeServer) => {
        const browserContext = browserLeafContext(
          context,
          activeServer,
          browserRecords,
          artifactResult,
          seedResult,
          rerunScope,
          retryState,
        )
        return callLeaf(deps.browserPass || deps.runBrowserPass, browserContext)
      })
    } catch (err) {
      return { done: low(`test-pilot browser execution failed: ${message(err)}`) }
    }
    const originProblem = browserOriginProblem(rawResults, serverContext)
    if (originProblem) {
      return { done: low(originProblem) }
    }

    try {
      aggregated = deciders.aggregateResults(rawResults)
    } catch (err) {
      return { done: low(`test-pilot result aggregation failed: ${message(err)}`) }
    }
    const aggregationProblem = resultAggregationProblem(aggregated)
    if (aggregationProblem) {
      return { done: low(aggregationProblem) }
    }

    retryState.browserEvidenceHead = retryState.currentHead
    retryState.browserPasses.push({
      head: retryState.browserEvidenceHead,
      rerunScope: rerunScope || { action: 'initial' },
      records: statusMap(aggregated),
    })
    completeLatestBatchAfter(retryState.fixBatchHistory, aggregated)
    combinedAggregated = mergeAggregatedEvidence(combinedAggregated, aggregated)

    const evidenceProblem = resultEvidenceProblem(combinedAggregated, records)
    if (!evidenceProblem) {
      const stabilization = await stabilizeReviewCode(deps, workItem, context, retryState, combinedAggregated, records)
      if (!stabilization.ok) {
        const wrote = await writeRetryStatus(deps, workItem, context, retryState, combinedAggregated, records, stabilization.reason)
        if (!wrote.ok) return { done: low(wrote.reason) }
        return { done: low(stabilization.reason) }
      }
      if (stabilization.changed) {
        stabilizationCycle += 1
        if (stabilizationCycle > 2) {
          const reason = 'review-code stabilization cycle cap reached'
          const wrote = await writeRetryStatus(deps, workItem, context, retryState, combinedAggregated, records, reason)
          if (!wrote.ok) return { done: low(wrote.reason) }
          return { done: low(reason) }
        }
        retryState.currentHead = stabilization.head || retryState.currentHead
        retryState.reviewStabilizationCycle = stabilizationCycle
        retryState.reviewCoverageHead = stabilization.reviewCoverageHead || stabilization.head
        rerunScope = { action: 'rerun_all', reason: 'review-code changed branch' }
        browserRecords = records
        combinedAggregated = null
        continue
      }
      retryState.reviewStabilizationCycle = stabilizationCycle
      retryState.reviewCoverageHead = stabilization.reviewCoverageHead || retryState.currentHead
      retryState.verifyPassedHead = stabilization.verifyPassedHead || retryState.currentHead
      return { combinedAggregated, retryState }
    }

    const failed = failedBrowserRecords(aggregated)
    if (!failed.length) {
      const retryWrite = await writeRetryStatus(deps, workItem, context, retryState, aggregated, records, evidenceProblem)
      if (!retryWrite.ok) return { done: low(retryWrite.reason) }
      return { done: low(evidenceProblem) }
    }

    const decision = await retryDecision(deps, aggregated, retryState.fixBatchHistory)
    if (decision.action !== 'fix_batch') {
      const reason = decision.reason || evidenceProblem
      const retryWrite = await writeRetryStatus(deps, workItem, context, retryState, aggregated, records, reason)
      if (!retryWrite.ok) return { done: low(retryWrite.reason) }
      return { done: low(reason) }
    }

    const failures = collectAppBugFailures(aggregated)
    if (!failures.length || failures.length !== failed.length) {
      const reason = 'one or more browser failures are not app-bug failures'
      const retryWrite = await writeRetryStatus(deps, workItem, context, retryState, aggregated, records, reason)
      if (!retryWrite.ok) return { done: low(retryWrite.reason) }
      return { done: low(reason) }
    }

    const fixBudget = await budgetCheck(deps, 'fix-batch', {
      workItem,
      failures,
      head: retryState.currentHead,
      fixBatchHistory: retryState.fixBatchHistory,
    })
    if (!fixBudget.ok) return { done: low(fixBudget.reason) }

    const summary = decision.summary || failureSummary(failures)
    const batch = {
      type: 'browser_fix_batch',
      batchNumber: retryState.fixBatchHistory.length + 1,
      intent: true,
      headBefore: retryState.browserEvidenceHead,
      failedStepIds: failures.map((failure) => failure.stepId),
      summary,
      scrubbedSummary: scrubFailureSummary(summary),
      before: statusMap(aggregated),
    }
    retryState.fixBatchHistory.push(batch)

    let fixResult
    try {
      fixResult = await dispatchFixBatch(failures, deps, {
        workItem,
        context,
        records,
        passResult: aggregated,
        fixBatchHistory: retryState.fixBatchHistory,
        batch,
      })
    } catch (err) {
      return { done: low(`test-pilot browser fix batch failed: ${message(err)}`) }
    }
    if (!fixResult || fixResult.ok === false || fixResult.action === 'park' || fixResult.confidence === 'low') {
      return { done: low((fixResult && (fixResult.reason || fixResult.message)) || 'test-pilot browser fix batch parked') }
    }

    const clean = await ensureCleanWorktreeAfterFix(fixResult, deps, { workItem, context, batch })
    if (!clean.ok) return { done: low(clean.reason) }

    const reconciled = await reconcileCommittedMutations(fixResult, retryState.fixBatchHistory, batch, deps, {
      workItem,
      context,
    })
    if (!reconciled.ok) return { done: low(reconciled.reason) }

    batch.intent = false
    batch.commitShas = normalizeShas(reconciled.commitShas || fixResult.commitShas || fixResult.commits || fixResult.shas)
    batch.changedFiles = normalizeStrings(reconciled.changedFiles || fixResult.changedFiles || fixResult.files)
    batch.headAfter = reconciled.head || fixResult.head || batch.commitShas[batch.commitShas.length - 1] || retryState.currentHead
    retryState.currentHead = batch.headAfter

    const dependencyMap = deps.dependencyMap || aggregated.dependencyMap || plan.dependencyMap || context.dependencyMap
    const rerunDecision = await retryDecision(
      deps,
      aggregated,
      retryState.fixBatchHistory,
      batch.changedFiles,
      dependencyMap,
    )
    rerunScope = normalizeRerunScope(rerunDecision)
    batch.rerunScope = rerunScope
    browserRecords = recordsForRerun(records, rerunScope)

    const wrote = await writeStatus(deps, workItem, milestoneStatus(context, workItem, 'fix-batch-ready', {
      planRecords: records,
      artifacts: artifactResult.artifacts,
      server: publicServerContext(serverContext),
      seed: seedResult.status || seedResult,
      fixBatchHistory: retryState.fixBatchHistory,
      browserEvidenceHead: retryState.browserEvidenceHead,
      currentHead: retryState.currentHead,
      lastBrowserResult: aggregated,
    }))
    if (!wrote.ok) return { done: low(wrote.reason) }
  }
}

// Phase 5: restore the seed baseline, publish the final artifacts + tested head, write the applicable
// status. Returns the high-confidence terminal, or low() on any park.
async function finalizeReadiness(deps, workItem, context, plan, records, retryState, combinedAggregated, artifactResult) {
  const baselineResult = await restoreFinalBaseline(deps, records, context, retryState)
  if (!baselineResult.ok) return low(baselineResult.reason)

  const finalArtifacts = await ensureFinalArtifacts(deps, {
    workItem,
    context,
    records,
    aggregated: combinedAggregated,
    artifacts: artifactResult.artifacts,
    baseline: baselineResult.baseline,
    retryState,
  })
  if (!finalArtifacts.ok) return low(finalArtifacts.reason)

  const publishResult = await publishFinalHead(deps, workItem, context, retryState, {
    records,
    artifacts: finalArtifacts.artifacts,
    baseline: baselineResult.baseline,
    aggregated: combinedAggregated,
  })
  if (!publishResult.ok) return low(publishResult.reason)

  const finalStatus = {
    schemaVersion: 1,
    verdict: 'applicable',
    workItem,
    branch: context.branch,
    head: retryState.currentHead,
    browserEvidenceHead: retryState.browserEvidenceHead,
    records: mergeAllowedSkippedResults(combinedAggregated.records, records),
    fixBatchHistory: retryState.fixBatchHistory,
    browserPasses: retryState.browserPasses,
    artifacts: finalArtifacts.artifacts,
    prPosting: finalArtifacts.posting || finalArtifacts.prPosting || artifactResult.posting || artifactResult.prPosting,
    baseline: baselineResult.baseline,
    review: context.review || { head: retryState.reviewCoverageHead || retryState.currentHead },
    verify: context.verify || { result: 'pass', head: retryState.verifyPassedHead || retryState.currentHead },
    remotePr: publishResult.remotePr || publishResult.remotePR || { head: retryState.currentHead },
  }
  if (combinedAggregated.coverageRationale || plan.coverageRationale) {
    finalStatus.coverageRationale = combinedAggregated.coverageRationale || plan.coverageRationale
  }
  if (combinedAggregated.fixes) finalStatus.fixes = combinedAggregated.fixes
  if (combinedAggregated.verify) finalStatus.verify = combinedAggregated.verify
  const wrote = await writeStatus(deps, workItem, finalStatus)
  if (!wrote.ok) return low(wrote.reason)

  return { confidence: 'high', assumptions: [] }
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
      // status already carries workItem (milestoneStatus / terminal statuses set it); the writer
      // contract is writeStatus(status) — don't pass a 2nd arg no implementation reads.
      const out = await deps.writeStatus(status)
      if (out && out.ok === false) return { ok: false, reason: out.reason || 'test-pilot status write failed' }
      if (out && out.read_back === false) return { ok: false, reason: out.reason || 'test-pilot status read-back mismatch' }
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

function browserLeafContext(context, server, records, artifacts, seed, rerunScope, retryState) {
  return {
    workItem: context.workItem,
    branch: context.branch,
    head: retryState && retryState.currentHead ? retryState.currentHead : context.head,
    profile: context.profile,
    browserTool: context.browserTool,
    baseUrl: server.baseUrl,
    allowedOrigins: server.allowedOrigins,
    server,
    records,
    allRecords: retryState ? retryState.allRecords : undefined,
    artifacts,
    seed,
    rerunScope,
    fixBatchHistory: retryState ? retryState.fixBatchHistory : undefined,
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

function resultAggregationProblem(aggregated) {
  if (!aggregated || typeof aggregated !== 'object') return 'test-pilot result aggregation returned no result'
  if (aggregated.confidence === 'low') return aggregated.reason || 'test-pilot result aggregation is low-confidence'
  if (aggregated.action === 'park' || aggregated.ok === false) return aggregated.reason || 'test-pilot result aggregation parked'
  if (!Array.isArray(aggregated.records) || aggregated.records.length === 0) return 'no browser-executed records were produced'
  return null
}

// Single source of truth for "this record is browser-derived evidence". MUST stay byte-for-byte
// equivalent to test_pilot_status.py `_browser_executed` (the mark-ready gate's check) — if the two
// drift, the in-phase readiness check and the mark-ready gate can disagree on the same status.
// The `browser === true` alias is the one the Python accepts that the JS previously omitted.
function browserExecutedRecord(record) {
  return !!record && typeof record === 'object' && (
    record.browserExecuted === true ||
    record.browser_executed === true ||
    record.browser === true ||
    record.kind === 'browser' ||
    record.type === 'browser'
  )
}

function resultEvidenceProblem(aggregated, records) {
  const aggregationProblem = resultAggregationProblem(aggregated)
  if (aggregationProblem) return aggregationProblem
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
    if (!browserExecutedRecord(record)) {
      return 'every browser step must have browser-derived pass/fail evidence'
    }
    seen.add(key)
  }
  for (const key of expected) {
    if (!seen.has(key)) return `browser-derived pass/fail evidence missing for step ${key}`
  }
  return null
}

function failedBrowserRecords(passResult) {
  const out = []
  for (const record of passRecords(passResult)) {
    const status = resultStatus(record)
    const key = stepKey(record)
    if ((status === 'failed' || status === 'fail') && key) out.push(record)
  }
  return out
}

function collectAppBugFailures(passResult) {
  return failedBrowserRecords(passResult)
    .filter(isAppBugFailure)
    .map((record) => {
      const key = stepKey(record)
      return Object.assign({}, record, {
        stepId: key,
        failureType: record.failureType || record.failure_type || record.kind || 'app_bug',
        summary: record.summary || record.notes || record.message || `browser step failed: ${key}`,
      })
    })
}

function passRecords(passResult) {
  if (!passResult || typeof passResult !== 'object') return []
  if (Array.isArray(passResult.records)) return passResult.records
  if (Array.isArray(passResult.steps)) return passResult.steps
  return []
}

function resultStatus(record) {
  return record && (record.status || record.result)
}

function isAppBugFailure(record) {
  const kind = record && (record.failureType || record.failure_type || record.kind)
  return kind === undefined || kind === null || ['app_bug', 'app-bug', 'application'].includes(kind)
}

function statusMap(passResult) {
  const out = {}
  for (const record of passRecords(passResult)) {
    const key = stepKey(record)
    if (key) out[key] = resultStatus(record)
  }
  return out
}

function mergeAggregatedEvidence(previous, current) {
  if (!previous) return Object.assign({}, current, { records: passRecords(current).map((record) => Object.assign({}, record)) })
  const byId = new Map()
  const order = []
  for (const record of passRecords(previous)) {
    const key = stepKey(record)
    if (!key) continue
    byId.set(key, Object.assign({}, record))
    order.push(key)
  }
  for (const record of passRecords(current)) {
    const key = stepKey(record)
    if (!key) continue
    if (!byId.has(key)) order.push(key)
    byId.set(key, Object.assign({}, record))
  }
  const merged = Object.assign({}, previous, current)
  merged.records = order.map((key) => byId.get(key)).filter(Boolean)
  return merged
}

function completeLatestBatchAfter(history, passResult) {
  const latest = latestFixBatch(history)
  if (latest && latest.after === undefined) latest.after = statusMap(passResult)
}

function latestFixBatch(history) {
  if (!Array.isArray(history)) return null
  for (let i = history.length - 1; i >= 0; i -= 1) {
    const entry = history[i]
    if (entry && (entry.type === 'browser_fix_batch' || entry.type === 'fix_batch')) return entry
  }
  return null
}

async function budgetCheck(deps, phase, payload) {
  const counts = payload && payload.counts ? payload.counts : {
    browserPasses: payload && typeof payload.browserPasses === 'number'
      ? payload.browserPasses
      : (payload && payload.rerunScope ? 1 : 0),
    browserFixBatches: payload && payload.fixBatchHistory ? payload.fixBatchHistory.length : 0,
  }
  try {
    if (typeof deps.budgetCheck === 'function') {
      const out = await deps.budgetCheck(phase, payload)
      if (out === false) return { ok: false, reason: `test-pilot budget exhausted before ${phase}` }
      if (out && out.ok === false) return { ok: false, reason: out.reason || `test-pilot budget exhausted before ${phase}` }
      if (out && out.action === 'park') return { ok: false, reason: out.reason || `test-pilot budget exhausted before ${phase}` }
      return { ok: true }
    }
    const out = deciders.budgetDecision(counts)
    if (out.action !== 'within_budget') {
      return { ok: false, reason: out.reason || `test-pilot budget exhausted before ${phase}` }
    }
    return { ok: true }
  } catch (err) {
    return { ok: false, reason: `test-pilot budget check failed before ${phase}: ${message(err)}` }
  }
}

async function retryDecision(deps, passResult, history, changedFiles, dependencyMap) {
  try {
    if (typeof deps.retryDecide === 'function') {
      return await deps.retryDecide(passResult, history, changedFiles, dependencyMap)
    }
    return deciders.retryDecisionFromFacts(passResult, history, changedFiles, dependencyMap)
  } catch (err) {
    return { action: 'park_retry_decision_failed', reason: `test-pilot retry decision failed: ${message(err)}` }
  }
}

function fixBatches(history) {
  return Array.isArray(history)
    ? history.filter((entry) => entry && (entry.type === 'browser_fix_batch' || entry.type === 'fix_batch'))
    : []
}

function failureSummary(failures) {
  return `Fix browser app failures: ${failures.map((failure) => failure.stepId).join(', ')}`
}

function scrubFailureSummary(summary) {
  return bounded(String(summary || '')
    .replace(/(?:\/private)?\/tmp\/\S+|\/[\w./-]+(?::\d+)?/g, ' ')
    .replace(/:\d+\b/g, ' ')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, ' ')
    .trim()
    .replace(/\s+/g, ' '))
}

async function dispatchFixBatch(failures, deps, details) {
  if (typeof deps.dispatchFixBatch !== 'function') throw new Error('required leaf is unavailable')
  return deps.dispatchFixBatch(failures, details)
}

async function ensureCleanWorktreeAfterFix(fixResult, deps, details) {
  if (typeof deps.ensureCleanWorktreeAfterFix === 'function') {
    try {
      const out = await deps.ensureCleanWorktreeAfterFix(fixResult, details)
      if (out && out.ok === false) return { ok: false, reason: out.reason || 'dirty fix leftovers after lease reset failed' }
      if (out && out.action === 'park') return { ok: false, reason: out.reason || 'dirty fix leftovers after lease reset failed' }
      return { ok: true }
    } catch (err) {
      return { ok: false, reason: `test-pilot clean worktree guard failed: ${message(err)}` }
    }
  }
  if (fixResult && (fixResult.dirty || fixResult.uncommitted || fixResult.untracked)) {
    return { ok: false, reason: 'dirty fix leftovers require an injected lease-fenced reset before retry' }
  }
  return { ok: true }
}

function reconcileCommittedMutations(fixResult, history, intent, deps, details) {
  if (deps && typeof deps.reconcileCommittedMutations === 'function') {
    return deps.reconcileCommittedMutations(fixResult, history, intent, details)
  }
  const commitShas = normalizeShas(fixResult && (fixResult.commitShas || fixResult.commits || fixResult.shas))
  const changedFiles = normalizeStrings(fixResult && (fixResult.changedFiles || fixResult.files))
  const head = fixResult && (fixResult.head || fixResult.headAfter)
  const committed = fixResult && (
    fixResult.cleanCommittedMutations ||
    fixResult.committedMutations ||
    fixResult.committed === true ||
    head ||
    commitShas.length
  )
  const hasHistory = Array.isArray(history) && history.includes(intent)
  if (committed && !commitShas.length && !hasHistory) {
    return {
      ok: false,
      reason: 'clean committed mutations without matching browser fix-batch history cannot be reconciled deterministically',
    }
  }
  return { ok: true, commitShas, changedFiles, head }
}

function normalizeRerunScope(decision) {
  if (!decision || typeof decision !== 'object') return { action: 'rerun_all' }
  if (decision.action === 'rerun_subset') {
    return {
      action: 'rerun_subset',
      stepIds: normalizeStrings(decision.stepIds),
      failedStepIds: normalizeStrings(decision.failedStepIds),
      affectedStepIds: normalizeStrings(decision.affectedStepIds),
    }
  }
  return {
    action: 'rerun_all',
    failedStepIds: normalizeStrings(decision.failedStepIds),
  }
}

function recordsForRerun(records, rerunScope) {
  if (!rerunScope || rerunScope.action !== 'rerun_subset') return records
  const allowed = new Set(normalizeStrings(rerunScope.stepIds))
  if (!allowed.size) return records
  return records
    .map((record) => {
      const steps = (record.steps || []).filter((step) => allowed.has(stepKey(step)))
      return Object.assign({}, record, { steps })
    })
    .filter((record) => record.steps.length)
}

async function stabilizeReviewCode(deps, workItem, context, retryState, aggregated, records) {
  const needsReview = fixBatches(retryState.fixBatchHistory).length > 0 ||
    (typeof deps.alwaysStabilizeReviewCode === 'function' && deps.alwaysStabilizeReviewCode())
  if (!needsReview && typeof deps.reviewCode !== 'function') {
    return { ok: true, changed: false, reviewCoverageHead: retryState.currentHead, verifyPassedHead: retryState.currentHead }
  }
  if (!needsReview && deps.requireReviewCode !== true) {
    return { ok: true, changed: false, reviewCoverageHead: retryState.currentHead, verifyPassedHead: retryState.currentHead }
  }
  if (retryState.reviewStabilizationCycle >= 2) {
    return { ok: false, reason: 'review-code stabilization cycle cap reached' }
  }
  if (typeof deps.reviewCode !== 'function') {
    return { ok: false, reason: 'review-code stabilization leaf unavailable' }
  }
  const cycle = (retryState.reviewStabilizationCycle || 0) + 1
  const before = retryState.currentHead
  let result
  try {
    result = await deps.reviewCode(workItem, {
      purpose: 'test-pilot-stabilization',
      worktree: context.worktree,
      expectedHead: before,
      runDirSuffix: `test-pilot-${cycle}-${before}`,
      cycle,
      browserFixBatchCount: fixBatches(retryState.fixBatchHistory).length,
      records,
      aggregated,
    })
  } catch (err) {
    return { ok: false, reason: `review-code stabilization failed: ${message(err)}` }
  }
  if (!result || result.ok === false || result.gate === 'changes-requested' ||
      (result.phaseResult && result.phaseResult.confidence === 'low')) {
    return { ok: false, reason: (result && (result.reason || (result.phaseResult && result.phaseResult.assumptions && result.phaseResult.assumptions[0]))) || 'review-code stabilization parked' }
  }
  if (result.terminal === 'clean-with-skips') {
    return { ok: false, reason: 'review-code stabilization clean-with-skips produced no covers stamp' }
  }
  const after = result.head || result.headAfter || result.currentHead || before
  const changed = after !== before || result.changed === true || result.mutated === true
  return {
    ok: true,
    changed,
    head: after,
    reviewCoverageHead: result.reviewCoverageHead || result.covers || after,
    verifyPassedHead: result.verifyPassedHead || result.verifyHead || after,
  }
}

async function restoreFinalBaseline(deps, records, context, retryState) {
  if (typeof deps.restoreBaseline !== 'function') {
    return { ok: true, baseline: context.baseline || { head: retryState.currentHead, restored: true } }
  }
  try {
    const out = await deps.restoreBaseline(records, {
      context,
      head: retryState.currentHead,
      fixBatchHistory: retryState.fixBatchHistory,
      reviewStabilizationCycle: retryState.reviewStabilizationCycle || 0,
    })
    if (!out || out.ok === false || out.action === 'park' || out.confidence === 'low') {
      return { ok: false, reason: (out && out.reason) || 'final seed baseline restore parked' }
    }
    const baseline = out.baseline || out.status || out
    if (!coversHead(baseline, retryState.currentHead)) {
      return { ok: false, reason: 'final seed baseline restore did not verify the final head' }
    }
    return { ok: true, baseline }
  } catch (err) {
    return { ok: false, reason: `final seed baseline restore failed: ${message(err)}` }
  }
}

async function ensureFinalArtifacts(deps, payload) {
  if (typeof deps.ensureFinalArtifacts !== 'function') {
    return { ok: true, artifacts: payload.artifacts }
  }
  try {
    const out = await deps.ensureFinalArtifacts(payload)
    if (!out || out.ok === false || out.action === 'park' || out.confidence === 'low') {
      return { ok: false, reason: (out && out.reason) || 'final test-pilot results artifact parked' }
    }
    const artifacts = out.artifacts || out
    if (!artifacts.plan || !artifacts.results) {
      return { ok: false, reason: 'final test-pilot plan/results artifacts missing' }
    }
    return Object.assign({ ok: true, artifacts }, out)
  } catch (err) {
    return { ok: false, reason: `final test-pilot artifact publish failed: ${message(err)}` }
  }
}

async function publishFinalHead(deps, workItem, context, retryState, payload) {
  if (typeof deps.publishReady !== 'function') {
    return { ok: true, remotePr: context.remotePr || context.remotePR || { head: retryState.currentHead } }
  }
  try {
    const out = await deps.publishReady(workItem, retryState.currentHead, Object.assign({
      context,
      branch: context.branch,
      head: retryState.currentHead,
    }, payload))
    if (!out || out.ok === false || out.action === 'park' || out.confidence === 'low') {
      return { ok: false, reason: (out && out.reason) || 'final tested head publish parked' }
    }
    if (out.read_back === false) {
      return { ok: false, reason: (out && out.reason) || 'final tested head read-back mismatch' }
    }
    const remotePr = out.remotePr || out.remotePR || { branch: context.branch, head: out.head || retryState.currentHead }
    if (!coversHead(remotePr, retryState.currentHead)) {
      return { ok: false, reason: 'remote PR head does not equal final tested head' }
    }
    return { ok: true, remotePr }
  } catch (err) {
    return { ok: false, reason: `final tested head publish failed: ${message(err)}` }
  }
}

function coversHead(value, head) {
  if (!value || typeof value !== 'object') return false
  return value.head === head || value.covers === head || value.browserEvidenceHead === head
}

async function writeRetryStatus(deps, workItem, context, retryState, aggregated, records, reason) {
  return writeStatus(deps, workItem, milestoneStatus(context, workItem, 'browser-retry-parked', {
    planRecords: records,
    fixBatchHistory: retryState.fixBatchHistory,
    reviewStabilizationCycle: retryState.reviewStabilizationCycle || 0,
    browserEvidenceHead: retryState.browserEvidenceHead,
    lastBrowserResult: aggregated,
    reason,
  }))
}

function normalizeStrings(values) {
  if (!Array.isArray(values)) return []
  return values.map((value) => value == null ? '' : String(value)).filter(Boolean)
}

function normalizeShas(values) {
  return normalizeStrings(values)
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

// Best-effort: stamp a parked status carrying WHY before an early low() return, so the mark-ready
// gate (and a human reading the sidecar) see the real cause instead of an opaque "status missing".
// Never changes the returned reason and never fails the phase if the write is unavailable/fails —
// the not_applicable path writes a status the same way; these early parks were the gap.
async function recordParkStatus(deps, workItem, context, reason) {
  if (!context) return
  try {
    await writeStatus(deps, workItem, milestoneStatus(context, workItem, 'parked', { reason }))
  } catch (_) { /* best-effort: low(reason) below still carries the real cause */ }
}

async function parkLow(deps, workItem, context, reason) {
  await recordParkStatus(deps, workItem, context, reason)
  return low(reason)
}

function low(reason) {
  return { confidence: 'low', assumptions: [reason] }
}

function message(err) {
  return err && err.message ? err.message : String(err || 'unknown')
}

module.exports = {
  testPilotPhase,
  collectAppBugFailures,
  dispatchFixBatch,
  ensureCleanWorktreeAfterFix,
  reconcileCommittedMutations,
  stabilizeReviewCode,
}
