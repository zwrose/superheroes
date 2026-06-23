// plugins/superheroes/lib/tests/showrunner_reviewcode_smoke.js
// Dev-time only (node, not CI): proves the #86 panel verdict -> gate vocabulary mapping.
// verdictToGate is a pure synchronous map, so this smoke needs no agent()/parallel() stubs.
const assert = require('assert')
const sr = require('../showrunner.js')

;(async () => {
  assert.strictEqual(sr.verdictToGate({ gate: 'clean', terminal: 'clean' }), 'passed',
    'a clean verdict -> passed')
  assert.strictEqual(sr.verdictToGate({ gate: 'blocking', terminal: 'halted' }), 'changes-requested',
    'a blocking verdict -> changes-requested')
  assert.strictEqual(sr.verdictToGate({ gate: 'cannot-certify', terminal: 'cannot-certify' }), 'changes-requested',
    'a cannot-certify verdict -> changes-requested (fail closed, never passed)')
  console.log('OK: panel verdict maps to gate (clean->passed, else->changes-requested)')
})().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
