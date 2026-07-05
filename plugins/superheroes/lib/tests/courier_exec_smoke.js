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

  // BUG B (live 2026-07-02 review-plan park): a `side-effect && save` chain answers with TWO
  // top-level JSON objects on two lines (set-gate line + save line). Neither the whole-string
  // JSON.parse nor the first-{…-last-} brace slice can parse two objects, so the parse must fall
  // to the individual lines and take the LAST parseable one (the SAVE result); require() then
  // validates THAT object.
  const SET_GATE = JSON.stringify({ ok: true, review: 'changes-requested', status: 'reviewed' })
  const SAVE = JSON.stringify({ ok: true, already: false, applied: true, journal_confirmed: true, checkpoint_confirmed: true })
  const TWO = { ok: true, stdout: SET_GATE + '\n' + SAVE }
  a = agentFrom([[TWO], [TWO]])   // both attempts answer identically (old code fails both -> clear throw)
  courier.setCourierAgent(a.fn)
  out = await courier.runCourierJson('read startup state', 'cmd',
    { require: ['ok', 'journal_confirmed', 'checkpoint_confirmed'], retryRealFailure: false })
  assert.strictEqual(out.applied, true, 'a two-object answer must resolve to the SAVE (last) object')
  assert.strictEqual(out.journal_confirmed, true)
  assert.strictEqual(a.calls(), 1, 'the two-object answer parses on the FIRST attempt (no retry burn)')

  // fenced variant: the whole two-object answer wrapped in one ``` fence.
  const FENCED_TWO = { ok: true, stdout: '```\n' + SET_GATE + '\n' + SAVE + '\n```' }
  a = agentFrom([[FENCED_TWO], [FENCED_TWO]])
  courier.setCourierAgent(a.fn)
  out = await courier.runCourierJson('read startup state', 'cmd',
    { require: ['ok', 'journal_confirmed', 'checkpoint_confirmed'], retryRealFailure: false })
  assert.strictEqual(out.applied, true, 'a fenced two-object answer must resolve to the SAVE (last) object')
  assert.strictEqual(a.calls(), 1)

  // && failure semantics preserved: when the side-effect fails (exit 1) the chain stops, so only
  // the ONE failure line is present; require() finds the save fields missing and the REAL side-
  // effect failure surfaces (never masked by the missing save line).
  a = agentFrom([[{ ok: true, stdout: JSON.stringify({ ok: false, reason: 'stale' }) }]])
  courier.setCourierAgent(a.fn)
  out = await courier.runCourierJson('read startup state', 'cmd',
    { require: ['ok', 'journal_confirmed', 'checkpoint_confirmed'], retryRealFailure: false })
  assert.strictEqual(out.ok, false, 'a lone side-effect failure line surfaces as ok:false')
  assert.strictEqual(out.reason, 'stale')

  // Regression guard: a single (possibly pretty-printed) object/array must NEVER be mis-sliced
  // into one of its own inner lines by the per-line fallback — the whole-string candidate wins.
  a = agentFrom([[{ ok: true, stdout: '{\n  "ok": true,\n  "items": [\n    {"a": 1},\n    {"b": 2}\n  ]\n}' }]])
  courier.setCourierAgent(a.fn)
  out = await courier.runCourierJson('read startup state', 'cmd', { require: ['ok'] })
  assert.deepStrictEqual(out.items, [{ a: 1 }, { b: 2 }], 'a pretty-printed single object parses whole, not per-line')
  assert.strictEqual(a.calls(), 1)

  // #218: a lazy courier parrots the embedded libRoot failure branch from the prompt WITHOUT
  // executing — runCourierJson accepts it as a real ok:false; runCourierMarkedJson rejects it
  // (no __SR_EXIT marker) and fails closed instead of fabricating a 'spine code root missing' park.
  const PARROT = JSON.stringify({ ok: false, reason: '__SR_LIBROOT_MISSING__' })
  courier.setCourierAgent(async (_prompt, opts) => {
    assert.strictEqual(opts.label, 'save phase progress')
    return PARROT
  })
  out = await courier.runCourierJson('save phase progress', 'cmd', { retryRealFailure: false })
  assert.strictEqual(out.reason, '__SR_LIBROOT_MISSING__', 'runCourierJson still accepts a parroted probe failure (unchanged)')

  let markedCalls = 0
  courier.setCourierAgent(async (_prompt, opts) => {
    assert.strictEqual(opts.label, 'save phase progress')
    markedCalls += 1
    return PARROT
  })
  await assert.rejects(
    () => courier.runCourierMarkedJson('save phase progress', 'cmd', { retryRealFailure: false }),
    /courier transport failed after retry/,
    'runCourierMarkedJson must NOT accept a marker-less parrot of the embedded failure branch',
  )
  assert.strictEqual(markedCalls, 6, 'runCourierMarkedJson exhausts 2 attempts × 3 dispatchMarked tries on a parroted answer')

  markedCalls = 0
  courier.setCourierAgent(async (_prompt, opts) => {
    assert.strictEqual(opts.label, 'save phase progress')
    markedCalls += 1
    return PARROT + '\n__SR_EXIT:0'
  })
  out = await courier.runCourierMarkedJson('save phase progress', 'cmd', { retryRealFailure: false })
  assert.strictEqual(out.reason, '__SR_LIBROOT_MISSING__',
    'runCourierMarkedJson accepts a genuine probe failure AFTER execution is proven')
  assert.strictEqual(markedCalls, 1, 'a marker-carrying genuine probe failure is not retried')

  console.log('ok: shared courier contract')
})().catch((e) => { console.error('FAIL:', e.message || e); process.exit(1) })
