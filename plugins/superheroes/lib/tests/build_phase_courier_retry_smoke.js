// plugins/superheroes/lib/tests/build_phase_courier_retry_smoke.js
// #115 courier-drop retry: the cheap haiku exec "courier" occasionally returns an EMPTY/garbled stdout
// for a command that ran fine (a live run parked because a journal_entry.py leaf returned stdout:"" and
// JSON.parse("") threw). The fix: execJson/execText retry the courier ONCE on an empty/unparseable
// stdout before failing closed (build-path commands are idempotent). A genuine {"ok":false} (a real
// durable-write failure) must STILL fail closed with NO retry. A clean {"ok":true} on the first call
// returns immediately (one exec call, no behavior change).
const assert = require('assert')
global.log = () => {}

function makeAgent(routes) {
  return async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    for (const [needle, resp] of routes) if (label === needle) return typeof resp === 'function' ? resp(prompt) : resp
    for (const [needle, resp] of routes) if (prompt.includes(needle)) return typeof resp === 'function' ? resp(prompt) : resp
    return ''
  }
}

const bp = require('../build_phase.js')
const TASK = { id: '1', title: 'A' }

;(async () => {
  // ---- (1) journal courier-DROP recovered by the retry (the OBSERVED failure) ----
  // The journal_entry.py exec returns stdout:"" (ok:true) on the FIRST call and {"ok":true} on the
  // SECOND. Pre-fix: JSON.parse("") threw -> jrnl={ok:false} -> the task PARKED. Post-fix: execJson
  // retries the courier once -> the second call's {"ok":true} recovers -> the task does NOT park.
  let journalCalls = 0
  global.agent = makeAgent([
    ['exec', (prompt) => {
      if (prompt.includes('build_state_cli.py gather')) return [{ index: 0, ok: true, stdout: JSON.stringify({ unmapped_commits: 0 }) }]
      if (prompt.includes('fence_cli.py')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
      if (prompt.includes('journal_entry.py')) {
        journalCalls += 1
        // empty stdout on attempt 1 (courier dropped it), real {"ok":true} on attempt 2.
        return [{ index: 0, ok: true, stdout: journalCalls === 1 ? '' : JSON.stringify({ ok: true }) }]
      }
      if (prompt.includes('record-reviewed')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
      if (prompt.includes('minor_rollup_cli.py')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
      return [{ index: 0, ok: true, stdout: '{}' }]
    }],
    ['worker', { ok: true, signal: 'ok', evidence: { testFailed: true, testPassed: true } }],
    ['review', { verdicts: { spec_compliance: 'pass', code_quality: 'pass' }, findings: [] }],
  ])
  let r = await bp.buildOneTask('wi', 5, TASK, 'superheroes/wi-abc', '1', '/tmp/wt')
  assert.strictEqual(r.parked, false, 'a dropped journal stdout must be recovered by the courier retry (not park)')
  assert.strictEqual(journalCalls, 2, 'the journal exec is retried exactly once on an empty stdout (2 calls total)')

  let malformedCalls = 0
  global.agent = makeAgent([
    ['exec', (prompt) => {
      if (prompt.includes('build_state_cli.py gather')) return [{ index: 0, ok: true, stdout: JSON.stringify({ unmapped_commits: 0 }) }]
      if (prompt.includes('fence_cli.py')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
      if (prompt.includes('journal_entry.py')) {
        malformedCalls += 1
        return [{ index: 0, ok: true, stdout: malformedCalls === 1 ? '{' : JSON.stringify({ ok: true }) }]
      }
      if (prompt.includes('record-reviewed')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
      return [{ index: 0, ok: true, stdout: '{}' }]
    }],
    ['worker', { ok: true, signal: 'ok', evidence: { testFailed: true, testPassed: true } }],
    ['review', { verdicts: { spec_compliance: 'pass', code_quality: 'pass' }, findings: [] }],
  ])
  r = await bp.buildOneTask('wi', 5, TASK, 'superheroes/wi-abc', '1', '/tmp/wt')
  assert.strictEqual(r.parked, false, 'a malformed journal stdout must be recovered by the shared courier retry')
  assert.strictEqual(malformedCalls, 2, 'malformed JSON is retried exactly once')

  // ---- (2) journal courier-drop on BOTH attempts -> park (fail-closed AFTER the retry) ----
  let journalCalls2 = 0
  global.agent = makeAgent([
    ['exec', (prompt) => {
      if (prompt.includes('build_state_cli.py gather')) return [{ index: 0, ok: true, stdout: JSON.stringify({ unmapped_commits: 0 }) }]
      if (prompt.includes('fence_cli.py')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
      if (prompt.includes('journal_entry.py')) { journalCalls2 += 1; return [{ index: 0, ok: true, stdout: '' }] }
      return [{ index: 0, ok: true, stdout: '{}' }]
    }],
    ['worker', { ok: true, signal: 'ok', evidence: {} }],
  ])
  r = await bp.buildOneTask('wi', 5, TASK, 'superheroes/wi-abc', '1', '/tmp/wt')
  assert.strictEqual(r.parked, true, 'an empty journal stdout on BOTH attempts must still park (fail-closed after retry)')
  assert.ok(/journal write failed/i.test(r.reason || ''), 'the record-before-advance park reason is preserved')
  assert.strictEqual(journalCalls2, 2, 'the journal exec is retried exactly once before failing closed (2 calls total)')

  // ---- (3) a genuine {"ok":false} journal (real durable-write failure) -> park with NO retry ----
  // A parseable {"ok":false} is a REAL failure, not a courier-drop: execJson returns it immediately
  // (the caller's !jrnl.ok parks), and the courier is NOT retried.
  let journalCalls3 = 0
  global.agent = makeAgent([
    ['exec', (prompt) => {
      if (prompt.includes('build_state_cli.py gather')) return [{ index: 0, ok: true, stdout: JSON.stringify({ unmapped_commits: 0 }) }]
      if (prompt.includes('fence_cli.py')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
      if (prompt.includes('journal_entry.py')) { journalCalls3 += 1; return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: false }) }] }
      return [{ index: 0, ok: true, stdout: '{}' }]
    }],
    ['worker', { ok: true, signal: 'ok', evidence: {} }],
  ])
  r = await bp.buildOneTask('wi', 5, TASK, 'superheroes/wi-abc', '1', '/tmp/wt')
  assert.strictEqual(r.parked, true, 'a genuine {"ok":false} journal write must park (fail closed)')
  assert.strictEqual(journalCalls3, 1, 'a genuine {"ok":false} is a real failure — NOT a courier-drop — so it is NOT retried')

  // ---- (4) clean happy path -> one exec call per command, no retry (drop-in, no behavior change) ----
  let journalCalls4 = 0
  global.agent = makeAgent([
    ['exec', (prompt) => {
      if (prompt.includes('build_state_cli.py gather')) return [{ index: 0, ok: true, stdout: JSON.stringify({ unmapped_commits: 0 }) }]
      if (prompt.includes('fence_cli.py')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
      if (prompt.includes('journal_entry.py')) { journalCalls4 += 1; return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }] }
      if (prompt.includes('record-reviewed')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
      return [{ index: 0, ok: true, stdout: '{}' }]
    }],
    ['worker', { ok: true, signal: 'ok', evidence: { testFailed: true, testPassed: true } }],
    ['review', { verdicts: { spec_compliance: 'pass', code_quality: 'pass' }, findings: [] }],
  ])
  r = await bp.buildOneTask('wi', 5, TASK, 'superheroes/wi-abc', '1', '/tmp/wt')
  assert.strictEqual(r.parked, false, 'a clean journal write completes the task')
  assert.strictEqual(journalCalls4, 1, 'a clean {"ok":true} on the first call returns immediately — exactly one exec, no retry')

  // ---- (5) read-gate courier-drop (execText) recovered by the retry ----
  // read-gate prints a PLAIN STRING. An empty stdout on attempt 1 -> retry -> 'passed' on attempt 2.
  // Pre-fix: an empty gate trimmed to '' -> park "tasks gate not passed ()". Post-fix: recovered.
  let gateCalls = 0
  global.agent = makeAgent([
    ['exec', (prompt) => {
      if (prompt.includes('read-gate')) { gateCalls += 1; return [{ index: 0, ok: true, stdout: gateCalls === 1 ? '' : 'passed' }] }
      if (prompt.includes('build_entry.py')) return [{ index: 0, ok: true, stdout: JSON.stringify({ branch: 'superheroes/wi-abc', path: '/tmp/wt' }) }]
      if (prompt.includes('task_list_cli.py')) return [{ index: 0, ok: true, stdout: JSON.stringify({ tasks: [], raw_task_heading_count: 0 }) }]
      return [{ index: 0, ok: true, stdout: '{}' }]
    }],
  ])
  const res = await bp.buildPhase('wi', 5)
  assert.strictEqual(res.confidence, 'high', 'a dropped read-gate stdout must be recovered by the execText retry (build proceeds to a zero-task finish)')
  assert.strictEqual(gateCalls, 2, 'the read-gate exec is retried exactly once on an empty stdout (2 calls total)')

  console.log('ok: build_phase courier-drop retry (execJson journal recover/park/no-retry-on-real-fail/happy-path + execText read-gate recover)')
})().catch((e) => { console.error('FAIL:', e.message || e); process.exit(1) })
