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
  await phaseOrderAndGate()
  console.log('OK: test-pilot phase skeleton smokes passed')
})().catch((e) => { console.error('FAIL:', e.stack || e.message); process.exit(1) })
