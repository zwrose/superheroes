const assert = require('assert')
const { testPilotPhase } = require('../test_pilot_phase.js')

function applicableContext(extra) {
  return Object.assign({
    branch: 'codex/example',
    head: 'abc123',
    profile: { baseUrl: 'http://localhost:3000' },
    browserTool: { kind: 'mcp' },
    allowedOrigins: ['http://localhost:3000'],
    diff: { files: ['src/app.tsx'] },
    detectors: { browser: true },
    pr: { number: 7 },
  }, extra || {})
}

function successfulDeps(labels) {
  return {
    resolveContext: async () => {
      labels.push('read test context')
      return applicableContext()
    },
    derivePlan: async () => {
      labels.push('plan-tests')
      return {
        records: [{
          branch: 'codex/example',
          steps: [{ id: 's1', instruction: 'open page', expected: 'page loads', scenarioIds: ['scenario-a'] }],
        }],
      }
    },
    preparePlanRecords: async (plan) => ({ action: 'ready', records: plan.records }),
    prepareTestRun: async () => {
      labels.push('prepare test run')
      return {
        artifactResult: { ok: true, artifacts: { plan: 'plan.md', results: 'results.md' }, posting: { ok: true } },
        serverContext: { verdict: 'ready_external', baseUrl: 'http://localhost:3000', allowedOrigins: ['http://localhost:3000'] },
        seedResult: { action: 'ready_for_browser', status: { seeded: true } },
      }
    },
    runBrowserPass: async () => {
      labels.push('browser-pass')
      return {
        source: 'browser',
        baseUrl: 'http://localhost:3000',
        steps: [{ id: 's1', status: 'passed', notes: 'observed page load' }],
      }
    },
    reviewCode: async (_workItem, opts) => ({
      gate: 'passed',
      head: opts.expectedHead,
      changed: false,
      reviewCoverageHead: opts.expectedHead,
      verifyPassedHead: opts.expectedHead,
    }),
    restoreBaseline: async (_records, details) => ({ ok: true, baseline: { head: details.head, restored: true } }),
    ensureFinalArtifacts: async (payload) => ({ ok: true, artifacts: Object.assign({}, payload.artifacts, { results: 'final-results.md' }), posting: { ok: true } }),
    publishReady: async (_workItem, head) => {
      labels.push('publish tested head')
      return { ok: true, read_back: true, remotePr: { branch: 'codex/example', head } }
    },
    writeStatus: async (status) => {
      if (!status.milestone) labels.push('write test status')
      return { ok: true, read_back: true }
    },
  }
}

;(async () => {
  const labels = []
  const out = await testPilotPhase('wi', 3, successfulDeps(labels))
  assert.strictEqual(out.confidence, 'high')
  assert.deepStrictEqual(labels, [
    'read test context',
    'plan-tests',
    'prepare test run',
    'browser-pass',
    'publish tested head',
    'write test status',
  ])

  const notApplicableLabels = []
  const notApplicableOut = await testPilotPhase('wi', 3, {
    resolveContext: async () => applicableContext({ diff: { files: ['docs/readme.md'] }, detectors: {} }),
    writeStatus: async (status) => {
      notApplicableLabels.push('write test status')
      assert.strictEqual(status.verdict, 'not_applicable')
      return { ok: true, read_back: true }
    },
  })
  assert.strictEqual(notApplicableOut.confidence, 'high')
  assert.deepStrictEqual(notApplicableLabels, ['write test status'])
  console.log('ok: test-pilot leaf budget')
})().catch((e) => { console.error('FAIL:', e.message || e); process.exit(1) })
