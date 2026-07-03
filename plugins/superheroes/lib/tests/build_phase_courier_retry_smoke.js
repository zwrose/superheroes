require('./_smoke_checkout_root.js')
// plugins/superheroes/lib/tests/build_phase_courier_retry_smoke.js
// #115 courier-drop retry: the cheap haiku exec "courier" occasionally returns an EMPTY/garbled stdout
// for a command that ran fine. execJson/runCourierJson retry ONCE on empty/unparseable stdout before
// failing closed. A genuine {"ok":false} (a real durable-write failure) must STILL fail closed with NO retry.
const assert = require('assert')
global.log = () => {}

function makeAgent(routes) {
  return async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    if (label === 'gather build state') {
      for (const [needle, resp] of routes) {
        if (needle === 'exec' && typeof resp === 'function') {
          const raw = resp('build_state_cli.py gather')
          const row = Array.isArray(raw) ? raw[0] : raw
          const stdout = (row && row.stdout != null) ? row.stdout : '{}'
          return [{ ok: true, stdout }]
        }
      }
    }
    for (const [needle, resp] of routes) if (label === needle) return typeof resp === 'function' ? resp(prompt) : resp
    for (const [needle, resp] of routes) if (prompt.includes(needle)) return typeof resp === 'function' ? resp(prompt) : resp
    return ''
  }
}

function builtOk() {
  return [{ ok: true, stdout: JSON.stringify({ ok: true, read_back: true, task: '1' }) }]
}

const bp = require('../build_phase.js')
const TASK = { id: '1', title: 'A' }

;(async () => {
  // ---- (1) record-task-built courier-DROP recovered by the retry ----
  let recordBuiltCalls = 0
  global.agent = makeAgent([
    ['exec', (prompt) => {
      if (prompt.includes('build_state_cli.py gather')) return [{ ok: true, stdout: JSON.stringify({ unmapped_commits: 0 }) }]
      if (prompt.includes('fence_cli.py')) return [{ ok: true, stdout: JSON.stringify({ ok: true }) }]
      return [{ ok: true, stdout: '{}' }]
    }],
    ['record task built', () => {
      recordBuiltCalls += 1
      return recordBuiltCalls === 1 ? [{ ok: true, stdout: '' }] : builtOk()
    }],
    ['record task reviewed', builtOk()],
    ['implement-task', { ok: true, signal: 'ok', evidence: { testFailed: true, testPassed: true } }],
    ['task-reviewer:r1', { verdicts: { spec_compliance: 'pass', code_quality: 'pass' }, findings: [] }],
  ])
  let r = await bp.buildOneTask('wi', 5, TASK, 'superheroes/wi-abc', '1', '/tmp/wt')
  assert.strictEqual(r.parked, false, 'a dropped record-built stdout must be recovered by the courier retry (not park)')
  assert.strictEqual(recordBuiltCalls, 2, 'record task built is retried exactly once on an empty stdout (2 calls total)')

  let malformedCalls = 0
  global.agent = makeAgent([
    ['exec', (prompt) => {
      if (prompt.includes('build_state_cli.py gather')) return [{ ok: true, stdout: JSON.stringify({ unmapped_commits: 0 }) }]
      if (prompt.includes('fence_cli.py')) return [{ ok: true, stdout: JSON.stringify({ ok: true }) }]
      return [{ ok: true, stdout: '{}' }]
    }],
    ['record task built', () => {
      malformedCalls += 1
      return malformedCalls === 1
        ? [{ ok: true, stdout: '{' }]
        : builtOk()
    }],
    ['record task reviewed', builtOk()],
    ['implement-task', { ok: true, signal: 'ok', evidence: { testFailed: true, testPassed: true } }],
    ['task-reviewer:r1', { verdicts: { spec_compliance: 'pass', code_quality: 'pass' }, findings: [] }],
  ])
  r = await bp.buildOneTask('wi', 5, TASK, 'superheroes/wi-abc', '1', '/tmp/wt')
  assert.strictEqual(r.parked, false, 'a malformed record-built stdout must be recovered by the shared courier retry')
  assert.strictEqual(malformedCalls, 2, 'malformed JSON is retried exactly once')

  // ---- (2) record-built drop on BOTH attempts -> park (fail-closed AFTER the retry) ----
  let recordBuiltCalls2 = 0
  global.agent = makeAgent([
    ['exec', (prompt) => {
      if (prompt.includes('build_state_cli.py gather')) return [{ ok: true, stdout: JSON.stringify({ unmapped_commits: 0 }) }]
      if (prompt.includes('fence_cli.py')) return [{ ok: true, stdout: JSON.stringify({ ok: true }) }]
      return [{ ok: true, stdout: '{}' }]
    }],
    ['record task built', () => { recordBuiltCalls2 += 1; return [{ ok: true, stdout: '' }] }],
    ['implement-task', { ok: true, signal: 'ok', evidence: {} }],
  ])
  r = await bp.buildOneTask('wi', 5, TASK, 'superheroes/wi-abc', '1', '/tmp/wt')
  assert.strictEqual(r.parked, true, 'an empty record-built stdout on BOTH attempts must still park (fail-closed after retry)')
  assert.ok(/record write failed|record-before-advance/i.test(r.reason || ''), 'the record-before-advance park reason is preserved')
  assert.strictEqual(recordBuiltCalls2, 2, 'record task built is retried exactly once before failing closed (2 calls total)')

  // ---- (3) a genuine {"ok":false} record-built -> park with NO retry ----
  let recordBuiltCalls3 = 0
  global.agent = makeAgent([
    ['exec', (prompt) => {
      if (prompt.includes('build_state_cli.py gather')) return [{ ok: true, stdout: JSON.stringify({ unmapped_commits: 0 }) }]
      if (prompt.includes('fence_cli.py')) return [{ ok: true, stdout: JSON.stringify({ ok: true }) }]
      return [{ ok: true, stdout: '{}' }]
    }],
    ['record task built', () => {
      recordBuiltCalls3 += 1
      return [{ ok: true, stdout: JSON.stringify({ ok: false, read_back: false, task: '1' }) }]
    }],
    ['implement-task', { ok: true, signal: 'ok', evidence: {} }],
  ])
  r = await bp.buildOneTask('wi', 5, TASK, 'superheroes/wi-abc', '1', '/tmp/wt')
  assert.strictEqual(r.parked, true, 'a genuine record-built failure must park (fail closed)')
  assert.strictEqual(recordBuiltCalls3, 1, 'a genuine failure is NOT retried')

  // ---- (4) clean happy path -> one courier call, no retry ----
  let recordBuiltCalls4 = 0
  global.agent = makeAgent([
    ['exec', (prompt) => {
      if (prompt.includes('build_state_cli.py gather')) return [{ ok: true, stdout: JSON.stringify({ unmapped_commits: 0 }) }]
      if (prompt.includes('fence_cli.py')) return [{ ok: true, stdout: JSON.stringify({ ok: true }) }]
      return [{ ok: true, stdout: '{}' }]
    }],
    ['record task built', () => { recordBuiltCalls4 += 1; return builtOk() }],
    ['record task reviewed', builtOk()],
    ['implement-task', { ok: true, signal: 'ok', evidence: { testFailed: true, testPassed: true } }],
    ['task-reviewer:r1', { verdicts: { spec_compliance: 'pass', code_quality: 'pass' }, findings: [] }],
  ])
  r = await bp.buildOneTask('wi', 5, TASK, 'superheroes/wi-abc', '1', '/tmp/wt')
  assert.strictEqual(r.parked, false, 'a clean record-built write completes the task')
  assert.strictEqual(recordBuiltCalls4, 1, 'a clean read-back on the first call returns immediately — exactly one call, no retry')

  // ---- (5) read-gate courier-drop (execText) recovered by the retry ----
  let gateCalls = 0
  global.agent = makeAgent([
    ['exec', (prompt) => {
      if (prompt.includes('read-gate')) { gateCalls += 1; return [{ ok: true, stdout: gateCalls === 1 ? '' : 'passed' }] }
      if (prompt.includes('build_entry.py')) return [{ ok: true, stdout: JSON.stringify({ branch: 'superheroes/wi-abc', path: '/tmp/wt' }) }]
      if (prompt.includes('task_list_cli.py')) return [{ ok: true, stdout: JSON.stringify({ tasks: [], raw_task_heading_count: 0 }) }]
      return [{ ok: true, stdout: '{}' }]
    }],
  ])
  const res = await bp.buildPhase('wi', 5)
  assert.strictEqual(res.confidence, 'high', 'a dropped read-gate stdout must be recovered by the execText retry (build proceeds to a zero-task finish)')
  assert.strictEqual(gateCalls, 2, 'the read-gate exec is retried exactly once on an empty stdout (2 calls total)')

  console.log('ok: build_phase courier-drop retry (record-built recover/park/no-retry-on-real-fail/happy-path + execText read-gate recover)')
})().catch((e) => { console.error('FAIL:', e.message || e); process.exit(1) })
