// plugins/superheroes/lib/tests/courier_retry_meter_smoke.js
// B5 (#315): the courier retry meter — a dispatch that needed >1 attempt must be counted, so retry
// pressure is visible before it becomes an outright failure. The detector this fix ships: drive the
// REAL retry loops of ALL FOUR courier variants (runCourierJson, runCourierText, runCourierMarkedJson,
// runCourierMarkedText — every path carrying a _recordRetry call; no monkeypatched accounting seam,
// only the injected command runner) with a fail-then-succeed sequence and assert the meter counts
// exactly one retry per dispatch; a first-try success must count zero.
//
// The Marked* variants ride the __SR_EXIT execution-marker protocol, so a "failed" first attempt here
// is a marker-present answer with EMPTY stdout before the marker (the loop's `empty stdout -> continue`
// branch), and the retry a marker-present answer with real payload.
const assert = require('assert')
const courier = require('../courier_exec.js')

function agentFrom(outputs) {
  let calls = 0
  return { calls: () => calls, fn: async () => { calls += 1; return outputs[calls - 1] } }
}

;(async () => {
  // 1. runCourierJson: empty stdout on attempt 0, valid JSON on attempt 1 -> exactly ONE retry.
  courier.resetCourierMeter()
  courier.setCourierAgent(agentFrom([
    [{ ok: true, stdout: '' }],
    [{ ok: true, stdout: JSON.stringify({ ok: true, gate: 'passed' }) }],
  ]).fn)
  let out = await courier.runCourierJson('read startup state', 'cmd', { require: ['ok', 'gate'] })
  assert.strictEqual(out.gate, 'passed')
  let m = courier.courierRetryTotals()
  assert.strictEqual(m.retried, 1, 'a fail-then-succeed JSON dispatch counts one retry')
  assert.strictEqual(m.byLabel['read startup state'], 1, 'the retry is attributed to its label')

  // 2. First-try success records nothing (a clean run must not inflate the meter).
  courier.resetCourierMeter()
  courier.setCourierAgent(agentFrom([
    [{ ok: true, stdout: JSON.stringify({ ok: true, gate: 'passed' }) }],
  ]).fn)
  await courier.runCourierJson('clean read', 'cmd', { require: ['ok', 'gate'] })
  assert.strictEqual(courier.courierRetryTotals().retried, 0, 'a first-try success records no retry')

  // 3. runCourierText: empty then non-empty -> one retry.
  courier.resetCourierMeter()
  courier.setCourierAgent(agentFrom([
    [{ ok: true, stdout: '' }],
    [{ ok: true, stdout: 'the answer' }],
  ]).fn)
  const t = await courier.runCourierText('text leaf', 'cmd')
  assert.strictEqual(t, 'the answer')
  assert.strictEqual(courier.courierRetryTotals().retried, 1, 'a fail-then-succeed text dispatch counts one retry')

  // 3b. runCourierMarkedJson: empty-before-marker on attempt 0, real payload on attempt 1 -> one retry.
  courier.resetCourierMeter()
  courier.setCourierAgent(agentFrom([
    [{ ok: true, stdout: '__SR_EXIT:0' }],                                   // marker present, empty stdout
    [{ ok: true, stdout: JSON.stringify({ ok: true, gate: 'passed' }) + '\n__SR_EXIT:0' }],
  ]).fn)
  const mj = await courier.runCourierMarkedJson('read startup state', 'cmd', { require: ['ok', 'gate'] })
  assert.strictEqual(mj.gate, 'passed')
  assert.strictEqual(courier.courierRetryTotals().retried, 1, 'a fail-then-succeed marked-JSON dispatch counts one retry')

  // 3c. runCourierMarkedText: same shape over the marker protocol -> one retry.
  courier.resetCourierMeter()
  courier.setCourierAgent(agentFrom([
    [{ ok: true, stdout: '__SR_EXIT:0' }],
    [{ ok: true, stdout: 'the marked answer\n__SR_EXIT:0' }],
  ]).fn)
  const mt = await courier.runCourierMarkedText('read startup state', 'cmd')
  assert.strictEqual(mt.trim(), 'the marked answer')
  assert.strictEqual(courier.courierRetryTotals().retried, 1, 'a fail-then-succeed marked-text dispatch counts one retry')

  // 4. Aggregate across two retried dispatches accumulates.
  courier.resetCourierMeter()
  courier.setCourierAgent(agentFrom([
    [{ ok: true, stdout: '' }], [{ ok: true, stdout: JSON.stringify({ ok: true }) }],
  ]).fn)
  await courier.runCourierJson('a', 'cmd', { require: ['ok'] })
  courier.setCourierAgent(agentFrom([
    [{ ok: true, stdout: '' }], [{ ok: true, stdout: JSON.stringify({ ok: true }) }],
  ]).fn)
  await courier.runCourierJson('b', 'cmd', { require: ['ok'] })
  assert.strictEqual(courier.courierRetryTotals().retried, 2, 'retries across dispatches accumulate')

  courier.resetCourierMeter()
  console.log('courier_retry_meter_smoke OK')
})().catch((e) => { console.error(e); process.exit(1) })
