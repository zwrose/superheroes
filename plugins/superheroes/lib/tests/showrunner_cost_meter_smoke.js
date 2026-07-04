// #130: cost_meter accumulator — proxy dispatch counting under the current phase, budget-measured
// output-token deltas across mark()->take(), take()'s snapshot-and-reset (which is how the phase's
// own persist leaf is excluded — by ordering, no flag), and the guarded budget read (a throwing
// spent() yields null, never throws).
const assert = require('assert')
const cm = require('../cost_meter.js')

;(async () => {
  cm.reset()
  globalThis.__SR_PHASE = 'workhorse'
  cm.mark('workhorse')                 // no budget -> unmeasured
  cm.record('claude-opus-4-8')
  cm.record('claude-haiku-4-5-20251001')
  cm.record('claude-haiku-4-5-20251001')
  let body = cm.take('workhorse')
  assert.strictEqual(body.dispatches.total, 3)
  assert.deepStrictEqual(body.dispatches.byModel, { 'claude-opus-4-8': 1, 'claude-haiku-4-5-20251001': 2 })
  assert.strictEqual(body.tokens.measured, false)
  assert.strictEqual(body.tokens.output, null)
  assert.strictEqual(body.tokens.source, 'none')
  assert.strictEqual(cm.isEmpty(body), false)
  // take() RESET the phase — a second take is empty (no double-count across a resumed phase)
  const empty = cm.take('workhorse')
  assert.strictEqual(empty.dispatches.total, 0)
  assert.strictEqual(cm.isEmpty(empty), true)

  // budget-measured path: output-token delta between mark() and take()
  cm.reset()
  let spent = 1000
  globalThis.__SR_BUDGET = { spent: () => spent }
  globalThis.__SR_PHASE = 'review-code'
  cm.mark('review-code')               // baselines at 1000
  cm.record('claude-sonnet-5')
  spent = 1500
  body = cm.take('review-code')
  assert.strictEqual(body.tokens.measured, true)
  assert.strictEqual(body.tokens.output, 500)
  assert.strictEqual(body.tokens.source, 'budget')

  // ordering exclusion: take() resets the phase, so a dispatch AFTER it (the persist leaf) lands in
  // a fresh bucket the next take() would report — never mixed into the just-emitted phase's count
  cm.reset()
  globalThis.__SR_PHASE = 'plan'
  cm.mark('plan'); cm.record('claude-opus-4-8')
  assert.strictEqual(cm.take('plan').dispatches.total, 1)
  cm.record('claude-opus-4-8')                 // the persist leaf's own dispatch, post-take()
  assert.strictEqual(cm.take('plan').dispatches.total, 1)   // isolated in the reset bucket, never emitted

  // guarded budget: a throwing spent() yields null (unmeasured), never throws
  cm.reset()
  globalThis.__SR_BUDGET = { spent: () => { throw new Error('nope') } }
  assert.strictEqual(cm.readSpent(), null)
  delete globalThis.__SR_BUDGET
  delete globalThis.__SR_PHASE

  console.log('ok: cost_meter accumulator')
})().catch((e) => { console.error('FAIL:', e.message || e); process.exit(1) })
