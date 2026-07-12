// plugins/superheroes/lib/tests/courier_denial_terminal_smoke.js
// #402 Part B: a classifier denial is TERMINAL for those bytes on ALL couriers. A deterministic denial
// re-denies, so re-dispatching the identical bytes is pointless AND reads as "tunneling." Every generic
// courier retry loop must, on a denial-signature answer:
//   (1) attempt EXACTLY once (no byte-identical re-dispatch);
//   (2) journal a scrubbed decline (base64 blobs redacted, length-clamped — JS-only, no extra leaf);
//   (3) fall to the caller's existing fail-closed path (throw CourierTransportError).
// A non-denial failure (a real command error / a marker-less parrot) still retries exactly as before.
// Run: node plugins/superheroes/lib/tests/courier_denial_terminal_smoke.js
const assert = require('assert')
const courier = require('../courier_exec.js')

const DENIAL = 'I cannot run this. Permission for this action was denied by the auto-mode classifier.'

// A counting agent whose every answer is the given text (drives the retry loops).
function constAgent(text) {
  let calls = 0
  return { calls: () => calls, fn: async () => { calls += 1; return text } }
}
// A courier-shape (array) agent for the non-marker runCourierJson/Text couriers.
function constArrayAgent(stdout, ok) {
  let calls = 0
  return { calls: () => calls, fn: async () => { calls += 1; return [{ index: 0, ok: ok !== false, stdout }] } }
}

function denialReasonUnit() {
  assert.strictEqual(courier.denialReason('all good, ran fine'), null, 'no denial signature -> null')
  const r = courier.denialReason(DENIAL)
  assert.ok(r && /permission for this action was denied/i.test(r), 'a denial signature -> a bounded reason')
  // base64-looking blobs are redacted (a staged payload must never leak into the reason).
  const blob = 'x'.repeat(40)
  assert.ok(!courier.denialReason('permission denied ' + blob).includes(blob), 'long base64-ish blobs are redacted')
  // length clamp (~200 chars + ellipsis).
  const long = courier.denialReason('permission denied ' + 'word '.repeat(200))
  assert.ok(long.length <= 201, 'the reason is length-clamped')
}

async function markerCouriersBreakEarly() {
  // runCourierMarkedText: a denial answer -> ONE dispatch, journaled decline, throw.
  let declined = []
  courier.setDeclineRecorder((label, reason) => declined.push({ label, reason }))
  let a = constAgent(DENIAL)
  courier.setCourierAgent(a.fn)
  await assert.rejects(() => courier.runCourierMarkedText('save phase progress', 'python3 x.py'),
    /courier transport failed/, 'runCourierMarkedText fails closed on a denial')
  assert.strictEqual(a.calls(), 1, 'runCourierMarkedText: EXACTLY one dispatch on a denial (no re-run)')
  assert.strictEqual(declined.length, 1, 'runCourierMarkedText journals exactly one decline')
  assert.ok(/permission for this action was denied/i.test(declined[0].reason), 'the decline carries the scrubbed reason')

  // runCourierMarkedJson: same one-attempt terminal behavior.
  declined = []
  a = constAgent(DENIAL)
  courier.setCourierAgent(a.fn)
  await assert.rejects(() => courier.runCourierMarkedJson('save phase progress', 'python3 x.py', { require: ['ok'] }),
    /courier transport failed/, 'runCourierMarkedJson fails closed on a denial')
  assert.strictEqual(a.calls(), 1, 'runCourierMarkedJson: EXACTLY one dispatch on a denial')
  assert.strictEqual(declined.length, 1, 'runCourierMarkedJson journals exactly one decline')

  // REGRESSION: a NON-denial marker-less parrot still exhausts the full 2×3 chain (unchanged).
  courier.setDeclineRecorder(null)
  let markedCalls = 0
  courier.setCourierAgent(async () => { markedCalls += 1; return JSON.stringify({ ok: false, reason: '__SR_LIBROOT_MISSING__' }) })
  await assert.rejects(() => courier.runCourierMarkedJson('save phase progress', 'cmd', { retryRealFailure: false }),
    /courier transport failed/, 'a non-denial parrot still fails closed')
  assert.strictEqual(markedCalls, 6, 'a non-denial parrot still burns 2×3 dispatches (denial break-early does NOT fire)')
}

async function plainCouriersBreakEarly() {
  // runCourierJson: a denial answer -> ONE dispatch, journaled decline, throw.
  let declined = []
  courier.setDeclineRecorder((label, reason) => declined.push({ label, reason }))
  let a = constArrayAgent(DENIAL)
  courier.setCourierAgent(a.fn)
  await assert.rejects(() => courier.runCourierJson('exec', 'gh issue create ...', { require: ['ok'] }),
    /courier transport failed/, 'runCourierJson fails closed on a denial')
  assert.strictEqual(a.calls(), 1, 'runCourierJson: EXACTLY one dispatch on a denial')
  assert.strictEqual(declined.length, 1, 'runCourierJson journals exactly one decline')

  // runCourierText: same.
  declined = []
  a = constArrayAgent(DENIAL)
  courier.setCourierAgent(a.fn)
  await assert.rejects(() => courier.runCourierText('exec', 'git commit ...'),
    /courier transport failed/, 'runCourierText fails closed on a denial')
  assert.strictEqual(a.calls(), 1, 'runCourierText: EXACTLY one dispatch on a denial')
  assert.strictEqual(declined.length, 1, 'runCourierText journals exactly one decline')

  // REGRESSION: a plain empty-stdout failure (no denial) still retries once (2 dispatches), unchanged.
  courier.setDeclineRecorder(null)
  a = constArrayAgent('')
  courier.setCourierAgent(a.fn)
  await assert.rejects(() => courier.runCourierJson('exec', 'cmd', { require: ['ok'] }),
    /courier transport failed/, 'a plain empty answer still fails closed after a retry')
  assert.strictEqual(a.calls(), 2, 'a non-denial empty answer still retries once (denial break-early does NOT fire)')

  // A REAL command failure carrying no denial signature is a result (ok:false), NOT a decline.
  a = constArrayAgent(JSON.stringify({ ok: false, error: 'real write failure' }))
  courier.setCourierAgent(a.fn)
  const out = await courier.runCourierJson('exec', 'cmd', { require: ['ok'], retryRealFailure: false })
  assert.strictEqual(out.ok, false, 'a non-denial command failure surfaces as a real ok:false result')
  assert.strictEqual(a.calls(), 1)
}

async function main() {
  denialReasonUnit()
  await markerCouriersBreakEarly()
  await plainCouriersBreakEarly()
  courier.setDeclineRecorder(null)
  console.log('ok: a denial is terminal on every courier — one attempt, journaled scrubbed decline, fail-closed (#402 Part B)')
}

main().catch((e) => { console.error('FAIL:', e.message, e.stack); process.exit(1) })
