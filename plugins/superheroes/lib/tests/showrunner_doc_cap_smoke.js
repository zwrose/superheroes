const assert = require('node:assert')
const test = require('node:test')
const shell = require('../review_panel_shell.js')

test('doc leg tally passes --doc-mode and max-rounds 3', async () => {
  let captured = null
  const ioApi = { join: (...p) => p.join('/'),
    runHelper: async (_bin, args) => { captured = args; return '{"terminal":"clean"}' } }
  await shell.tallyRoundDecider({ runDir: '/tmp/r', round: 1, roster: ['a'], maxRounds: 3,
    gate: 'clean', confidence: 'high', missing: [], presentBlocking: 0, fixStatus: 'completed',
    verifyResult: null, enterConfirmation: false, ioApi, docMode: true })
  assert.ok(captured.includes('--doc-mode'), 'doc leg must pass --doc-mode')
  const i = captured.indexOf('--max-rounds'); assert.strictEqual(captured[i + 1], '3')
})

test('doc leg plan-round ALSO passes --doc-mode (the round-scheduling decider, not just tally)', async () => {
  let captured = null
  const ioApi = { join: (...p) => p.join('/'),
    runHelper: async (_bin, args) => { captured = args; return '{"ok":true,"enterConfirmation":false,"dimensions":{},"carried":{},"latestCoverageDecisionIds":[]}' } }
  await shell.planRoundDecider({ runDir: '/tmp/r', round: 1, roster: ['a'],
    changedSubjects: null, justMarked: false, coverageTarget: null, ioApi, docMode: true })
  assert.ok(captured.includes('--doc-mode'), 'doc leg plan-round must ALSO pass --doc-mode')
})
