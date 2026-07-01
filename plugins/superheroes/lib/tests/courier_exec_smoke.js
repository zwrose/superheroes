const assert = require('assert')
const courier = require('../courier_exec.js')

function agentFrom(outputs) {
  let calls = 0
  return {
    calls: () => calls,
    fn: async (_prompt, opts) => {
      calls += 1
      assert.strictEqual(opts.label, 'read startup state')
      return outputs[calls - 1]
    },
  }
}

;(async () => {
  let a = agentFrom([[{ ok: true, stdout: JSON.stringify({ ok: true, gate: 'passed' }) }]])
  courier.setCourierAgent(a.fn)
  let out = await courier.runCourierJson('read startup state', 'cmd', {
    require: ['ok', 'gate'],
  })
  assert.strictEqual(out.gate, 'passed')
  assert.strictEqual(a.calls(), 1)

  a = agentFrom([
    [{ ok: true, stdout: '' }],
    [{ ok: true, stdout: JSON.stringify({ ok: true, gate: 'passed' }) }],
  ])
  courier.setCourierAgent(a.fn)
  out = await courier.runCourierJson('read startup state', 'cmd', { require: ['ok', 'gate'] })
  assert.strictEqual(out.gate, 'passed')
  assert.strictEqual(a.calls(), 2)

  a = agentFrom([
    [{ ok: true, stdout: '{' }],
    [{ ok: true, stdout: JSON.stringify({ ok: true, gate: 'passed' }) }],
  ])
  courier.setCourierAgent(a.fn)
  out = await courier.runCourierJson('read startup state', 'cmd', { require: ['ok', 'gate'] })
  assert.strictEqual(out.gate, 'passed')
  assert.strictEqual(a.calls(), 2)

  a = agentFrom([
    [{ ok: true, stdout: JSON.stringify({ ok: true }) }],
    [{ ok: true, stdout: JSON.stringify({ ok: true, gate: 'passed' }) }],
  ])
  courier.setCourierAgent(a.fn)
  out = await courier.runCourierJson('read startup state', 'cmd', { require: ['ok', 'gate'] })
  assert.strictEqual(out.gate, 'passed')
  assert.strictEqual(a.calls(), 2)

  a = agentFrom([[{ ok: true, stdout: JSON.stringify({ ok: false, error: 'real write failure' }) }]])
  courier.setCourierAgent(a.fn)
  out = await courier.runCourierJson('read startup state', 'cmd', { require: ['ok'], retryRealFailure: false })
  assert.strictEqual(out.ok, false)
  assert.strictEqual(a.calls(), 1)

  a = agentFrom([[{ ok: true, stdout: '' }], [{ ok: true, stdout: '' }]])
  courier.setCourierAgent(a.fn)
  await assert.rejects(
    () => courier.runCourierJson('read startup state', 'cmd', { require: ['ok'] }),
    /courier transport failed after retry/,
  )
  assert.strictEqual(a.calls(), 2)
  console.log('ok: shared courier contract')
})().catch((e) => { console.error('FAIL:', e.message || e); process.exit(1) })
