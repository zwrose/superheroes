const assert = require('assert')
const { testPilotPhase } = require('../test_pilot_phase.js')

function context(overrides) {
  return Object.assign({
    workItem: 'wi',
    branch: 'feature/wi',
    head: 'abc123',
    diff: { files: ['web/app.tsx'] },
    detectors: { browser: true },
    profile: { baseUrl: 'http://localhost:3000' },
    browserTool: { kind: 'mcp' },
    allowedOrigins: ['http://localhost:3000'],
    pr: { number: 11 },
    store: '/tmp/store',
  }, overrides || {})
}

async function successfulRun() {
  const labels = []
  let preparedLogged = false
  const out = await testPilotPhase('wi', 3, {
    resolveContext: async () => { labels.push('read test context'); return context() },
    planTests: async () => {
      labels.push('plan-tests')
      return { records: [{ branch: 'feature/wi', steps: [{ id: 's1', instruction: 'open', expected: 'loaded' }] }] }
    },
    preparePlanRecords: async (plan) => ({ action: 'ready', records: plan.records }),
    prepareArtifacts: async () => {
      if (!preparedLogged) { labels.push('prepare test run'); preparedLogged = true }
      return { ok: true, artifacts: { plan: 'plan.md', results: 'results.md' }, posting: { ok: true } }
    },
    resolveServer: async () => {
      if (!preparedLogged) { labels.push('prepare test run'); preparedLogged = true }
      return { verdict: 'ready_external', baseUrl: 'http://localhost:3000', allowedOrigins: ['http://localhost:3000'] }
    },
    seedRecords: async () => {
      if (!preparedLogged) { labels.push('prepare test run'); preparedLogged = true }
      return { action: 'ready_for_browser', status: { seeded: true } }
    },
    browserPass: async () => {
      labels.push('browser-pass')
      return { source: 'browser', steps: [{ id: 's1', status: 'passed', notes: 'ok' }] }
    },
    writeStatus: async (status) => {
      if (status.verdict === 'not_applicable' || status.verdict === 'applicable') labels.push('write test status')
      return { ok: true, read_back: true }
    },
    ensureFinalArtifacts: async () => ({ ok: true, artifacts: { plan: 'plan.md', results: 'results.md' }, posting: { ok: true } }),
    publishReady: async (_workItem, head) => {
      labels.push('publish tested head')
      return { ok: true, read_back: true, remotePr: { branch: 'feature/wi', head } }
    },
  })
  assert.strictEqual(out.confidence, 'high')
  assert.deepStrictEqual(labels, [
    'read test context',
    'plan-tests',
    'prepare test run',
    'browser-pass',
    'publish tested head',
    'write test status',
  ])
}

async function notApplicableRun() {
  const labels = []
  const out = await testPilotPhase('wi', 3, {
    resolveContext: async () => { labels.push('read test context'); return context({ diff: { files: ['docs/readme.md'] }, detectors: {} }) },
    writeStatus: async () => { labels.push('write test status'); return { ok: true, read_back: true } },
  })
  assert.strictEqual(out.confidence, 'high')
  assert.deepStrictEqual(labels, ['read test context', 'write test status'])
}

;(async () => {
  await successfulRun()
  await notApplicableRun()
  console.log('ok: test-pilot leaf budget labels')
})().catch((e) => { console.error('FAIL:', e.message || e); process.exit(1) })
