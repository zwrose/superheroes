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

  // Fence-tolerant parsing (live 2026-07-02: haiku wrapped the 'read startup state' output in
  // ```json fences twice in a row -> CourierTransportError -> park 'unreadable', while the exec
  // path's equally-fenced response was accepted by _parseExecResult). The courier must accept
  // the same shapes: fenced, prose-wrapped fence, prose-around-bare-object, clean (covered above).
  const OBJ = JSON.stringify({ ok: true, gate: 'passed' })
  a = agentFrom([[{ ok: true, stdout: '```json\n' + OBJ + '\n```' }]])
  courier.setCourierAgent(a.fn)
  out = await courier.runCourierJson('read startup state', 'cmd', { require: ['ok', 'gate'] })
  assert.strictEqual(out.gate, 'passed', 'fenced JSON object must parse')
  assert.strictEqual(a.calls(), 1, 'fenced JSON must be accepted on the FIRST attempt (no retry burn)')

  a = agentFrom([[{ ok: true, stdout: 'Here is the output:\n```\n' + OBJ + '\n```\nDone.' }]])
  courier.setCourierAgent(a.fn)
  out = await courier.runCourierJson('read startup state', 'cmd', { require: ['ok', 'gate'] })
  assert.strictEqual(out.gate, 'passed', 'prose-prefixed fenced JSON must parse')
  assert.strictEqual(a.calls(), 1)

  a = agentFrom([[{ ok: true, stdout: 'The result is ' + OBJ + ' as requested.' }]])
  courier.setCourierAgent(a.fn)
  out = await courier.runCourierJson('read startup state', 'cmd', { require: ['ok', 'gate'] })
  assert.strictEqual(out.gate, 'passed', 'prose around a bare JSON object must parse (brace slice)')
  assert.strictEqual(a.calls(), 1)

  // Still fail-closed: prose with NO recoverable object retries then throws.
  a = agentFrom([[{ ok: true, stdout: 'no json here' }], [{ ok: true, stdout: 'still none' }]])
  courier.setCourierAgent(a.fn)
  await assert.rejects(
    () => courier.runCourierJson('read startup state', 'cmd', { require: ['ok'] }),
    /courier transport failed after retry/,
  )
  assert.strictEqual(a.calls(), 2)
  console.log('ok: shared courier contract')
})().catch((e) => { console.error('FAIL:', e.message || e); process.exit(1) })
