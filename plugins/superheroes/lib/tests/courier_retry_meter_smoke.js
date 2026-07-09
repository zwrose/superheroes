// plugins/superheroes/lib/tests/courier_retry_meter_smoke.js
// B5 (#315): the courier retry meter — a dispatch that needed >1 attempt must be counted, so retry
// pressure is visible before it becomes an outright failure. The detector this fix ships: drive the
// REAL runCourierJson/Text/MarkedJson retry loops (no monkeypatched accounting seam — only the
// injected command runner) with a fail-then-succeed sequence and assert the meter counts exactly one
// retry per dispatch; a first-try success must count zero.
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
