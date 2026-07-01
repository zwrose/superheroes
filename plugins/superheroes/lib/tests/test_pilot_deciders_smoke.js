const assert = require('assert')
const deciders = require('../test_pilot_deciders.js')

;(async () => {
  const notApplicable = deciders.applicabilityDecision(
    { files: ['docs/readme.md'] },
    {},
    {},
    null,
  )
  assert.strictEqual(notApplicable.verdict, 'not_applicable')

  const aggregated = deciders.aggregateResults({
    source: 'browser',
    steps: [{ id: 's1', status: 'passed', notes: 'ok' }],
  })
  assert.strictEqual(aggregated.action, 'aggregated')
  assert.strictEqual(aggregated.records[0].status, 'passed')

  const missingEvidence = deciders.aggregateResults({ steps: [{ id: 's1', status: 'passed' }] })
  assert.strictEqual(missingEvidence.action, 'park')
  assert.match(missingEvidence.reason, /browser-derived evidence/)

  const exhausted = deciders.retryDecisionFromFacts(
    { records: [{ stepId: 's1', status: 'failed', failureType: 'app_bug' }] },
    [
      { type: 'browser_fix_batch', summary: 'Fix browser app failures: s1' },
      { type: 'browser_fix_batch', summary: 'Fix browser app failures: s1' },
      { type: 'browser_fix_batch', summary: 'Fix browser app failures: s1' },
    ],
  )
  assert.strictEqual(exhausted.action, 'park_cap_reached')
  assert.ok(exhausted.reason)

  const retryable = deciders.retryDecisionFromFacts(
    { records: [{ stepId: 's1', status: 'failed', failureType: 'app_bug' }] },
    [],
  )
  assert.strictEqual(retryable.action, 'fix_batch')
  assert.deepStrictEqual(retryable.failedStepIds, ['s1'])

  console.log('ok: test-pilot pure deciders')
})().catch((e) => { console.error('FAIL:', e.message || e); process.exit(1) })
