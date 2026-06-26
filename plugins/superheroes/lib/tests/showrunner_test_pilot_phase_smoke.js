// plugins/superheroes/lib/tests/showrunner_test_pilot_phase_smoke.js
const assert = require('assert')

global.agent = async (prompt) => {
  if (prompt.includes('phase_step_cli.py')) {
    return { action: 'park_unexpected_gate', reason: 'browser verification failed' }
  }
  if (prompt.includes('journal_entry.py')) return { ok: true }
  return { ok: true }
}
global.log = () => {}

const sr = require('../showrunner.js')
const { testPilotPhase } = require('../test_pilot_phase.js')

function baseContext(extra) {
  return Object.assign({
    branch: 'codex/example',
    head: 'abc123',
    profile: { baseUrl: 'http://localhost:3000' },
    browserTool: { kind: 'mcp' },
    allowedOrigins: ['http://localhost:3000'],
  }, extra || {})
}

function applicableDeps(extra) {
  return Object.assign({
    resolveContext: async () => baseContext(),
    decideApplicability: async () => ({ verdict: 'applicable' }),
    derivePlan: async () => ({
      records: [{
        branch: 'codex/example',
        steps: [{ id: 's1', instruction: 'open page', expected: 'page loads', scenarioIds: ['scenario-a'] }],
      }],
    }),
    preparePlanRecords: async (_plan, context) => ({
      action: 'ready',
      records: [{
        branch: context.branch,
        steps: [{ id: 's1', instruction: 'open page', expected: 'page loads', scenarioIds: ['scenario-a'] }],
      }],
    }),
    prepareArtifacts: async () => ({ ok: true, artifacts: { plan: 'plan.md', results: 'results.md' }, posting: { ok: true } }),
    resolveServer: async (_context) => ({ verdict: 'ready_external', baseUrl: 'http://localhost:3000', allowedOrigins: ['http://localhost:3000'], teardownRequired: false }),
    withManagedServer: async (serverContext, run) => run(serverContext),
    seedRecords: async (_records) => ({ action: 'ready_for_browser', status: { seeded: true } }),
    runBrowserPass: async () => ({
      source: 'browser',
      baseUrl: 'http://localhost:3000',
      steps: [{ id: 's1', status: 'passed', notes: 'observed page load' }],
    }),
    aggregateResults: async () => ({
      action: 'aggregated',
      records: [{ stepId: 's1', status: 'passed', notes: 'observed page load', browserExecuted: true }],
      coverageRationale: 'covers branch state',
    }),
    writeStatus: async () => ({ ok: true }),
  }, extra || {})
}

async function notApplicableProceeds() {
  const statuses = []
  const out = await testPilotPhase('wi', 3, {
    resolveContext: async () => baseContext(),
    decideApplicability: async () => ({ verdict: 'not_applicable', rationale: 'docs-only change' }),
    writeStatus: async (status) => { statuses.push(status); return { ok: true } },
  })
  assert.strictEqual(out.confidence, 'high')
  assert.strictEqual(statuses.length, 1)
  assert.strictEqual(statuses[0].verdict, 'not_applicable')
  assert.strictEqual(statuses[0].head, 'abc123')
}

async function uncertainApplicabilityParks() {
  const out = await testPilotPhase('wi', 3, {
    resolveContext: async () => baseContext(),
    decideApplicability: async () => ({ verdict: 'park', reason: 'uncertain signals' }),
    writeStatus: async () => { throw new Error('status should not be written') },
  })
  assert.strictEqual(out.confidence, 'low')
  assert.match(out.assumptions[0], /uncertain signals/)
}

async function emptyApplicablePlanParks() {
  let browserRan = false
  const out = await testPilotPhase('wi', 3, {
    resolveContext: async () => baseContext(),
    decideApplicability: async () => ({ verdict: 'applicable' }),
    derivePlan: async () => ({ records: [] }),
    runBrowserPass: async () => { browserRan = true },
  })
  assert.strictEqual(out.confidence, 'low')
  assert.match(out.assumptions[0], /plan is empty/)
  assert.strictEqual(browserRan, false)
}

async function missingSetupParksBeforeBrowser() {
  let browserRan = false
  const out = await testPilotPhase('wi', 3, {
    resolveContext: async () => baseContext({ profile: null }),
    decideApplicability: async () => ({ verdict: 'applicable' }),
    runBrowserPass: async () => { browserRan = true },
  })
  assert.strictEqual(out.confidence, 'low')
  assert.match(out.assumptions[0], /calibration\/profile/)
  assert.strictEqual(browserRan, false)
}

async function missingBrowserToolParksBeforeBrowser() {
  let browserRan = false
  const out = await testPilotPhase('wi', 3, {
    resolveContext: async () => baseContext({ browserTool: null }),
    decideApplicability: async () => ({ verdict: 'applicable' }),
    runBrowserPass: async () => { browserRan = true },
  })
  assert.strictEqual(out.confidence, 'low')
  assert.match(out.assumptions[0], /browser tool/)
  assert.strictEqual(browserRan, false)
}

async function applicableFlowOrdersDurableMilestones() {
  const calls = []
  const statuses = []
  const out = await testPilotPhase('wi', 3, applicableDeps({
    derivePlan: async () => { calls.push('derivePlan'); return { records: [{
      branch: 'codex/example',
      steps: [{ id: 's1', instruction: 'open page', expected: 'page loads', scenarioIds: ['scenario-a'] }],
    }] } },
    preparePlanRecords: async (plan) => { calls.push('preparePlanRecords'); return { action: 'ready', records: plan.records } },
    prepareArtifacts: async () => { calls.push('prepareArtifacts'); return { ok: true, artifacts: { plan: 'plan.md', results: 'results.md' }, posting: { ok: true } } },
    resolveServer: async () => { calls.push('resolveServer'); return { verdict: 'ready_external', baseUrl: 'http://localhost:3000', allowedOrigins: ['http://localhost:3000'], teardownRequired: false } },
    seedRecords: async () => { calls.push('seedRecords'); return { action: 'ready_for_browser', status: { seeded: true } } },
    runBrowserPass: async (browserContext) => {
      calls.push('runBrowserPass')
      assert.strictEqual(browserContext.baseUrl, 'http://localhost:3000')
      assert.deepStrictEqual(browserContext.allowedOrigins, ['http://localhost:3000'])
      return { source: 'browser', baseUrl: 'http://localhost:3000', steps: [{ id: 's1', status: 'passed', notes: 'observed page load' }] }
    },
    aggregateResults: async () => { calls.push('aggregateResults'); return { action: 'aggregated', records: [{ stepId: 's1', status: 'passed', browserExecuted: true }] } },
    writeStatus: async (status) => { calls.push(`writeStatus:${status.milestone || status.verdict}`); statuses.push(status); return { ok: true } },
  }))
  assert.strictEqual(out.confidence, 'high')
  assert.deepStrictEqual(calls, [
    'derivePlan',
    'writeStatus:plan-derived',
    'preparePlanRecords',
    'writeStatus:plan-records-ready',
    'prepareArtifacts',
    'writeStatus:artifacts-ready',
    'resolveServer',
    'writeStatus:server-ready',
    'seedRecords',
    'writeStatus:seed-ready',
    'runBrowserPass',
    'aggregateResults',
    'writeStatus:applicable',
  ])
  assert.strictEqual(statuses[statuses.length - 1].verdict, 'applicable')
  assert.strictEqual(statuses[statuses.length - 1].records[0].stepId, 's1')
}

async function invalidPreparedRecordsParkBeforeArtifactsSeedAndBrowser() {
  const calls = []
  const out = await testPilotPhase('wi', 3, applicableDeps({
    preparePlanRecords: async () => ({ action: 'park', reason: 'plan validation failed: bad record' }),
    prepareArtifacts: async () => { calls.push('artifacts') },
    seedRecords: async () => { calls.push('seed') },
    runBrowserPass: async () => { calls.push('browser') },
  }))
  assert.strictEqual(out.confidence, 'low')
  assert.match(out.assumptions[0], /plan validation failed/)
  assert.deepStrictEqual(calls, [])
}

async function generatedInRepoPlanStoreParksBeforeWorktreeMutation() {
  const calls = []
  const out = await testPilotPhase('wi', 3, applicableDeps({
    derivePlan: async () => ({ records: [{
      branch: 'codex/example',
      store: { location: 'in_repo', generated: true },
      steps: [{ id: 's1', instruction: 'open page', expected: 'page loads' }],
    }] }),
    preparePlanRecords: async () => { calls.push('preparePlanRecords') },
    seedRecords: async () => { calls.push('seed') },
  }))
  assert.strictEqual(out.confidence, 'low')
  assert.match(out.assumptions[0], /generated in-repo plan store/)
  assert.deepStrictEqual(calls, [])
}

async function resumePreservesHumanStateAndAvoidsDuplicateIds() {
  let preparedRecords
  const previous = [{
    stepId: 's1',
    checkboxState: 'checked',
    humanChecked: true,
    status: 'passed',
    browserExecuted: true,
  }]
  const out = await testPilotPhase('wi', 3, applicableDeps({
    readStatus: async () => ({ verdict: 'applicable', records: previous }),
    derivePlan: async () => ({ records: [{
      branch: 'codex/example',
      steps: [
        { id: 's1', instruction: 'open page again', expected: 'page loads', scenarioIds: ['scenario-a'] },
        { id: 's2', instruction: 'click action', expected: 'action completes', scenarioIds: ['scenario-b'] },
      ],
    }] }),
    preparePlanRecords: async (plan) => { preparedRecords = plan.records; return { action: 'ready', records: plan.records } },
    runBrowserPass: async () => ({
      source: 'browser',
      baseUrl: 'http://localhost:3000',
      steps: [
        { id: 's1', status: 'passed', notes: 'observed page load' },
        { id: 's2', status: 'passed', notes: 'observed action' },
      ],
    }),
    aggregateResults: async () => ({
      action: 'aggregated',
      records: [
        { stepId: 's1', status: 'passed', browserExecuted: true },
        { stepId: 's2', status: 'passed', browserExecuted: true },
      ],
    }),
  }))
  assert.strictEqual(out.confidence, 'high')
  assert.strictEqual(preparedRecords[0].steps[0].checkboxState, 'checked')
  const ids = preparedRecords.flatMap((record) => record.steps.map((step) => step.id))
  assert.deepStrictEqual(ids, ['s1', 's2'])
}

async function skippedStepRequiresPreservationFields() {
  const out = await testPilotPhase('wi', 3, applicableDeps({
    derivePlan: async () => ({ records: [{
      branch: 'codex/example',
      steps: [{ id: 's1', instruction: 'open page', expected: 'page loads', status: 'skipped', removalReason: 'no longer reachable' }],
    }] }),
  }))
  assert.strictEqual(out.confidence, 'low')
  assert.match(out.assumptions[0], /skipped step preservation/)
}

async function managedServerTearsDownOnBrowserFailure() {
  const calls = []
  const out = await testPilotPhase('wi', 3, applicableDeps({
    resolveServer: async () => ({
      verdict: 'managed',
      command: ['npm', 'run', 'dev'],
      shell: false,
      baseUrl: 'http://localhost:3000',
      allowedOrigins: ['http://localhost:3000'],
      teardownRequired: true,
    }),
    withManagedServer: async (serverContext, run) => {
      assert.strictEqual(serverContext.shell, false)
      calls.push('start')
      try {
        return await run(serverContext)
      } finally {
        calls.push('teardown')
      }
    },
    runBrowserPass: async () => { throw new Error('browser crashed') },
  }))
  assert.strictEqual(out.confidence, 'low')
  assert.match(out.assumptions[0], /browser execution failed/)
  assert.deepStrictEqual(calls, ['start', 'teardown'])
}

async function offOriginBrowserResultsPark() {
  const out = await testPilotPhase('wi', 3, applicableDeps({
    runBrowserPass: async () => ({
      source: 'browser',
      baseUrl: 'http://evil.example',
      steps: [{ id: 's1', status: 'passed', notes: 'off origin' }],
    }),
  }))
  assert.strictEqual(out.confidence, 'low')
  assert.match(out.assumptions[0], /off-origin/)
}

async function nonBrowserEvidenceParksBeforeReadiness() {
  const out = await testPilotPhase('wi', 3, applicableDeps({
    aggregateResults: async () => ({ action: 'aggregated', records: [{ stepId: 's1', status: 'passed' }] }),
  }))
  assert.strictEqual(out.confidence, 'low')
  assert.match(out.assumptions[0], /browser-derived pass\/fail evidence/)
}

async function phaseOrderAndGate() {
  const idx = sr.PHASES.indexOf('test-pilot')
  assert.ok(idx > sr.PHASES.indexOf('draft-PR'), 'test-pilot follows draft-PR')
  assert.ok(idx < sr.PHASES.indexOf('mark-ready'), 'test-pilot precedes mark-ready')

  let markReadyReached = false
  const out = await sr.runPhases('wi', sr.PHASES.indexOf('test-pilot'), {
    testPilot: async () => ({ confidence: 'low', assumptions: ['browser verification failed'] }),
    markReady: async () => { markReadyReached = true; return { phaseResult: { confidence: 'high', assumptions: [] }, sideEffect: { ready: true } } },
  })
  assert.strictEqual(out.outcome, 'parked')
  assert.strictEqual(out.phase, 'test-pilot')
  assert.strictEqual(markReadyReached, false)
}

;(async () => {
  await notApplicableProceeds()
  await uncertainApplicabilityParks()
  await emptyApplicablePlanParks()
  await missingSetupParksBeforeBrowser()
  await missingBrowserToolParksBeforeBrowser()
  await applicableFlowOrdersDurableMilestones()
  await invalidPreparedRecordsParkBeforeArtifactsSeedAndBrowser()
  await generatedInRepoPlanStoreParksBeforeWorktreeMutation()
  await resumePreservesHumanStateAndAvoidsDuplicateIds()
  await skippedStepRequiresPreservationFields()
  await managedServerTearsDownOnBrowserFailure()
  await offOriginBrowserResultsPark()
  await nonBrowserEvidenceParksBeforeReadiness()
  await phaseOrderAndGate()
  console.log('OK: test-pilot phase skeleton smokes passed')
})().catch((e) => { console.error('FAIL:', e.stack || e.message); process.exit(1) })
