// plugins/superheroes/lib/tests/showrunner_handoff_delivery_smoke.js
// #397 Task 16 (FR-3 + UFR-5): the tasks produce leaf must (a) receive the plan review's hand-off
// list spliced into the author prompt and (b) journal a `handoff_provided` event — delivered > 0
// when the hand-off was read, or delivered: 0 + reason when it was absent/unreadable — so the
// receipt is honest either way. This smoke drives producePhase('tasks', ...) directly through the
// injectable seams: globalThis.agent (the exec courier + the author dispatch) and global.io.runHelper
// (the review_handoff.py read AND the handoff_provided journal append), asserting BOTH the prompt
// splice and the journaled receipt.
'use strict'
const assert = require('node:assert')
const test = require('node:test')
const { defaultIo } = require('../io_seam.js')
const sr = require('../showrunner.js')

// Build the injectable seams for a single producePhase('tasks') run.
//   handoffRead: the {ok,...} object the mocked `review_handoff.py read` returns.
// Returns { run, capturedPrompt(), handoffAppends() }.
function harness(handoffRead) {
  let authored = false
  let capturedPrompt = null
  const handoffAppends = []

  globalThis.agent = async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    if (label.indexOf('author-') === 0) {
      capturedPrompt = String(prompt)
      authored = true                          // the doc is now "written" — the post-check goes usable
      return { status: 'ok', notify: [] }
    }
    // exec() dumb-pipe: the prompt lists shell commands and expects a [{index,ok,stdout}] array.
    const p = String(prompt)
    if (p.includes('front_half_usable.py')) {
      // pre-author draft is NOT usable (so we author); post-author it is (so producePhase certifies).
      return [{ index: 0, ok: true, stdout: JSON.stringify(
        { usable: authored, expected: '', missing_sections: [], placeholder: false }) }]
    }
    return [{ index: 0, ok: true, stdout: '{}' }]
  }

  global.io = Object.assign({}, defaultIo, {
    async runHelper(cmd, args) {
      const a = args || []
      // the handoff_provided journal append: python3 -c '<...journal.append..."handoff_provided"...>'
      if (a[0] === '-c' && typeof a[1] === 'string' && a[1].includes('handoff_provided')) {
        let payload = null
        try { payload = JSON.parse(a[3]) } catch (_) { payload = { raw: a[3] } }
        handoffAppends.push(payload)
        return { ok: true, status: 0, stdout: '', stderr: '' }
      }
      // review_handoff.py read: return the canned hand-off object
      if (a.some((x) => String(x).includes('review_handoff.py')) && a.includes('read')) {
        return { ok: true, status: 0, stdout: JSON.stringify(handoffRead), stderr: '' }
      }
      return { ok: true, status: 0, stdout: '{}', stderr: '' }
    },
  })

  return {
    run: () => sr.producePhase('tasks', 'wi-handoff'),
    capturedPrompt: () => capturedPrompt,
    handoffAppends: () => handoffAppends,
  }
}

function reset() { delete global.io; delete globalThis.agent }

test('tasks produce leaf receives the hand-off AND journals handoff_provided (delivered > 0)', async () => {
  const h = harness({
    ok: true,
    findings: [
      { identity: 'plan.md::retry constant is two literals', planSection: '## Architecture',
        text: 'the retry constant appears as two separate literals' },
      { identity: 'plan.md::no named test for fallback', planSection: '## Testing',
        text: 'no named unit test for the fallback branch' },
    ],
    counts: { distinct: 2 },
  })
  const result = await h.run()
  assert.strictEqual(result.confidence, 'high', 'the tasks author certified the draft')

  // (a) the author prompt carries the hand-off entries verbatim
  const prompt = h.capturedPrompt()
  assert.ok(prompt, 'the author was dispatched')
  assert.ok(prompt.includes('Hand-off from the plan review'), 'prompt has the hand-off section')
  assert.ok(prompt.includes('the retry constant appears as two separate literals'),
    'prompt splices the first hand-off finding text')
  assert.ok(prompt.includes('no named unit test for the fallback branch'),
    'prompt splices the second hand-off finding text')

  // (b) a handoff_provided event was journaled with delivered == the hand-off count
  const appends = h.handoffAppends()
  assert.strictEqual(appends.length, 1, 'exactly one handoff_provided journal append')
  assert.strictEqual(appends[0].doc, 'tasks')
  assert.strictEqual(appends[0].delivered, 2, 'delivered equals the hand-off finding count')

  reset()
})

test('tasks produce leaf journals handoff_provided with delivered: 0 + reason when absent', async () => {
  const h = harness({ ok: false, reason: 'absent' })
  const result = await h.run()
  assert.strictEqual(result.confidence, 'high', 'produce proceeds without the hand-off (advisory only)')

  // the prompt discloses the hand-off was unavailable and does NOT claim findings were consumed
  const prompt = h.capturedPrompt()
  assert.ok(prompt.includes('Hand-off from the plan review'), 'prompt still has the hand-off section')
  assert.ok(/not available|absent|unreadable/i.test(prompt), 'prompt discloses the hand-off was unavailable')

  // the honest receipt: delivered 0 + the reason (UFR-5)
  const appends = h.handoffAppends()
  assert.strictEqual(appends.length, 1, 'exactly one handoff_provided journal append')
  assert.strictEqual(appends[0].doc, 'tasks')
  assert.strictEqual(appends[0].delivered, 0, 'delivered is 0 when the hand-off was absent')
  assert.strictEqual(appends[0].reason, 'absent', 'the reason is journaled honestly')

  reset()
})

test('tasks produce leaf discloses handoff_provided journal failure in the author prompt (UFR-5)', async () => {
  const h = harness({
    ok: true,
    findings: [{ identity: 'plan.md::x', planSection: '## A', text: 'finding one' }],
    counts: { distinct: 1 },
  })
  const origRunHelper = global.io.runHelper
  global.io = Object.assign({}, global.io, {
    async runHelper(cmd, args) {
      const a = args || []
      if (a[0] === '-c' && typeof a[1] === 'string' && a[1].includes('handoff_provided')) {
        return { ok: false, status: 1, stdout: '', stderr: 'event append failed: disk full' }
      }
      return origRunHelper.call(this, cmd, args)
    },
  })
  const result = await h.run()
  assert.strictEqual(result.confidence, 'high', 'produce still proceeds when the journal receipt fails')

  const prompt = h.capturedPrompt()
  assert.ok(prompt.includes('Hand-off from the plan review'), 'prompt still carries the hand-off section')
  assert.ok(prompt.includes('finding one'), 'prompt still splices the hand-off finding')
  assert.ok(/could NOT journal the handoff_provided receipt/i.test(prompt),
    'prompt discloses the journal write failure')
  assert.ok(/disk full|event append failed/i.test(prompt),
    'prompt names the journal error detail')
  assert.strictEqual(h.handoffAppends().length, 0, 'no handoff_provided append succeeded')

  reset()
})
