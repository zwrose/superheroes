// plugins/superheroes/lib/tests/showrunner_handoff_delivery_smoke.js
// #397 Task 16 (FR-3 + UFR-5): the tasks produce leaf must (a) receive the plan review's hand-off
// list spliced into the author prompt and (b) journal a `handoff_provided` event — delivered > 0
// when the hand-off was read, or delivered: 0 + reason when it was absent/unreadable — so the
// receipt is honest either way. This smoke drives producePhase('tasks', ...) with a REAL
// plan-handoff.json planted in a REAL docs dir (via globalThis.__SR_DOC_DIRS, the same seam
// showrunner_fronthalf_docdir_smoke.js plants): the file is written by the actual
// `review_handoff.py write` CLI and the produce path's `review_handoff.py read` dispatch runs the
// actual Python against it (defaultIo.runHelper fall-through) — the docs-dir file integration and
// the missing-file path are exercised for real, not stubbed. Only the journal append and the
// unrelated exec pipes stay mocked.
'use strict'
const assert = require('node:assert')
const test = require('node:test')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')
const { defaultIo } = require('../io_seam.js')
const sr = require('../showrunner.js')

const RH = path.join(__dirname, '..', 'review_handoff.py')

// Plant a REAL plan-handoff.json in docsDir through the actual writer CLI (the same code the
// plan-review terminal runs), so the read side below exercises the true write→read pair.
async function plantHandoff(docsDir, findings) {
  const staged = path.join(docsDir, 'staged-findings.json')
  fs.writeFileSync(staged, JSON.stringify(findings))
  const out = await defaultIo.runHelper('python3', [
    RH, 'write', '--docs-dir', docsDir, '--work-item', 'wi-handoff', '--findings', staged,
  ])
  assert.ok(out.ok, `real review_handoff.py write must succeed: ${out.stderr}`)
  const ans = JSON.parse(out.stdout)
  assert.ok(ans.ok && fs.existsSync(path.join(docsDir, 'plan-handoff.json')),
    'a real plan-handoff.json exists in the planted docs dir')
  return ans
}

// Build the injectable seams for a single producePhase('tasks') run against a REAL docs dir.
// Returns { run, capturedPrompt(), handoffAppends(), docsDir }.
function harness() {
  const docsDir = fs.mkdtempSync(path.join(os.tmpdir(), `handoff-smoke-${process.pid}-`))
  globalThis.__SR_DOC_DIRS = { 'wi-handoff': docsDir }

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
      // review_handoff.py read: NOT stubbed — run the REAL CLI against the REAL planted docs dir
      // (this is the integration Task 16 requires the smoke to verify, including the missing-file
      // path when nothing was planted).
      if (a.some((x) => String(x).includes('review_handoff.py')) && a.includes('read')) {
        return defaultIo.runHelper.call(this, cmd, args)
      }
      return { ok: true, status: 0, stdout: '{}', stderr: '' }
    },
  })

  return {
    run: () => sr.producePhase('tasks', 'wi-handoff'),
    capturedPrompt: () => capturedPrompt,
    handoffAppends: () => handoffAppends,
    docsDir,
  }
}

function reset() {
  delete global.io
  delete globalThis.agent
  delete globalThis.__SR_DOC_DIRS
}

test('tasks produce leaf receives a REAL planted hand-off AND journals handoff_provided (delivered > 0)', async () => {
  const h = harness()
  await plantHandoff(h.docsDir, [
    { file: 'plan.md', title: 'retry constant is two literals', severity: 'Minor',
      planSection: '## Architecture',
      summary: 'the retry constant appears as two separate literals' },
    { file: 'plan.md', title: 'no named test for fallback', severity: 'Minor',
      planSection: '## Testing',
      summary: 'no named unit test for the fallback branch' },
  ])
  const result = await h.run()
  assert.strictEqual(result.confidence, 'high', 'the tasks author certified the draft')

  // (a) the author prompt carries the hand-off entries the REAL read returned from disk
  const prompt = h.capturedPrompt()
  assert.ok(prompt, 'the author was dispatched')
  assert.ok(prompt.includes('Hand-off from the plan review'), 'prompt has the hand-off section')
  assert.ok(prompt.includes('the retry constant appears as two separate literals'),
    'prompt splices the first hand-off finding text')
  assert.ok(prompt.includes('no named unit test for the fallback branch'),
    'prompt splices the second hand-off finding text')

  // (b) a handoff_provided event was journaled with delivered == the on-disk hand-off count
  const appends = h.handoffAppends()
  assert.strictEqual(appends.length, 1, 'exactly one handoff_provided journal append')
  assert.strictEqual(appends[0].doc, 'tasks')
  assert.strictEqual(appends[0].delivered, 2, 'delivered equals the hand-off finding count')

  reset()
})

test('tasks produce leaf journals handoff_provided with delivered: 0 + reason when the file is absent', async () => {
  const h = harness()   // planted docs dir exists, but NO plan-handoff.json was written
  const result = await h.run()
  assert.strictEqual(result.confidence, 'high', 'produce proceeds without the hand-off (advisory only)')

  // the REAL read hit the real missing-file path and returned {ok:false, reason:'absent'}
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
  const h = harness()
  await plantHandoff(h.docsDir, [
    { file: 'plan.md', title: 'x finding one', severity: 'Minor',
      planSection: '## A', summary: 'finding one' },
  ])
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
