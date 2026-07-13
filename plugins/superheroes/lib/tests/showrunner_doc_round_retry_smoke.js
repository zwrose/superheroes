// Task 22 (#397 UFR-4): doc-review per-round tally retry — 2 attempts before parking; code leg unchanged.
'use strict'
const assert = require('node:assert')
const test = require('node:test')
const fs = require('fs')
const os = require('os')
const path = require('path')

global.log = () => {}

function freshRunDir() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'doc-round-retry-'))
}

function baseTallyArgs(runDir, legKind) {
  return {
    runDir,
    round: 1,
    roster: ['Spec'],
    maxRounds: 3,
    roundFindings: {
      Spec: {
        status: 'run',
        findings: [],
        confidence: 'high',
        verificationReceipt: { artifact: 'test:round-1', chain: [{ step: 'citation', evidence: 'ok' }] },
      },
    },
    legKind,
    runId: 'test-run',
    ioApi: { join: path.join, runHelper: async () => ({ stdout: '{"terminal":"clean","reason":"ok"}' }) },
  }
}

test('doc leg: one transient tallyRoundDecider failure is absorbed by retry', async () => {
  const shell = require('../review_panel_shell.js')
  const orig = shell.tallyRoundDecider
  let calls = 0
  shell.tallyRoundDecider = async () => {
    calls += 1
    if (calls === 1) throw new Error('transient dispatch error')
    return { terminal: 'clean', reason: 'doc round clean' }
  }
  try {
    const result = await shell.tallyRound(baseTallyArgs(freshRunDir(), { docMode: true }))
    assert.strictEqual(calls, 2, 'transient failure then success = 2 decider calls')
    assert.strictEqual(result.terminal, 'clean', 'successful retry yields clean terminal')
  } finally {
    shell.tallyRoundDecider = orig
  }
})

test('doc leg: exhausted retries halt with reason naming the failure', async () => {
  const shell = require('../review_panel_shell.js')
  const orig = shell.tallyRoundDecider
  let calls = 0
  const errMsg = 'persistent courier dispatch error'
  shell.tallyRoundDecider = async () => {
    calls += 1
    throw new Error(errMsg)
  }
  try {
    const result = await shell.tallyRound(baseTallyArgs(freshRunDir(), { docMode: true }))
    assert.strictEqual(calls, 2, 'DOC_ROUND_RETRY_ATTEMPTS=2 tries, never a third')
    assert.strictEqual(result.terminal, 'halted')
    assert.ok(result.reason.includes(errMsg), 'reason names the failure')
  } finally {
    shell.tallyRoundDecider = orig
  }
})

test('code leg: zero retry — first throw halts immediately', async () => {
  const shell = require('../review_panel_shell.js')
  const orig = shell.tallyRoundDecider
  let calls = 0
  shell.tallyRoundDecider = async () => {
    calls += 1
    throw new Error('code leg failure')
  }
  try {
    const result = await shell.tallyRound(baseTallyArgs(freshRunDir(), {}))
    assert.strictEqual(calls, 1, 'code leg: no retry, exactly one attempt')
    assert.strictEqual(result.terminal, 'halted')
  } finally {
    shell.tallyRoundDecider = orig
  }
})
