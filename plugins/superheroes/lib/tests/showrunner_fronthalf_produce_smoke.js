// Smoke: producePhase resumes a usable draft (no authoring), re-produces when not usable, and parks
// (low confidence) when the produce leaf fails or yields no usable draft. Stubs the leaves.
// usableDraft verdict is computed Python-side at the IO boundary (front_half_usable.py
// --emit-signals calls front_half.is_usable_draft and returns a small {usable, recorded, expected}
// signal). The spine reads signals.usable directly — no JS twin call on the live doc text.
// The agent stub must:
//   - intercept exec (label='exec') for: front_half_usable --emit-signals, appendNotify (append-notify).
//   - intercept produce-* label for authoring.
//   - NOT intercept model_tier_resolve, front_half_usable --write-marker, or append-notify via 'lib'.
const assert = require('assert')
const sr = require('../showrunner.js')
global.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))
global.log = () => {}

// Small boundary signals: verdict computed Python-side. No large doc text in the pipe.
const USABLE_SIGNAL = JSON.stringify({ usable: true, recorded: 'abc123', expected: 'abc123' })
const NOT_USABLE_SIGNAL = JSON.stringify({ usable: false, recorded: '', expected: '' })

function agentWith({ usableSeq, authored, notifyOk = true }) {
  const seq = usableSeq.slice()
  let produceCalls = 0
  const fn = async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    if (label === 'exec') {
      if (prompt.includes('emit-signals')) return [{ index: 0, ok: true, stdout: seq.shift() ? USABLE_SIGNAL : NOT_USABLE_SIGNAL }]
      if (prompt.includes('append-notify')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: notifyOk }) }]
      // Any other exec (e.g. persist, journal, checkpoint) — return ok
      return [{ index: 0, ok: true, stdout: '' }, { index: 1, ok: true, stdout: '' }]
    }
    if (label === 'lib') {
      // model_tier_resolve and front_half_usable --write-marker must NOT appear via 'lib' after Task 12.
      if (prompt.includes('model_tier_resolve')) throw new Error('model_tier_resolve dispatched as cmdRunner — must be in-process JS twin')
      if (prompt.includes('front_half_usable') && prompt.includes('--write-marker')) throw new Error('write-marker dispatched as cmdRunner — must be folded into author agent')
      return { ok: true }
    }
    if (label.startsWith('produce-')) { produceCalls += 1; return authored }
    return null
  }
  fn.produceCalls = () => produceCalls
  return fn
}

async function main() {
  // (a) already-usable draft -> resume, never author (FR-8).
  let ag = agentWith({ usableSeq: [true], authored: { status: 'ok' } })
  global.agent = ag
  let r = await sr.producePhase('plan', 'wi')
  assert.strictEqual(r.confidence, 'high', 'usable draft -> high')
  assert.strictEqual(ag.produceCalls(), 0, 'a usable draft is NOT re-authored')

  // (b) not usable -> author -> (marker written by author internally) -> re-check usable -> high.
  ag = agentWith({ usableSeq: [false, true], authored: { status: 'ok' } })
  global.agent = ag
  r = await sr.producePhase('plan', 'wi')
  assert.strictEqual(r.confidence, 'high', 'authored + usable -> high')
  assert.strictEqual(ag.produceCalls(), 1, 'the produce leaf authored once')

  // (c) produce leaf fails (null) -> low confidence (parks, UFR-4).
  ag = agentWith({ usableSeq: [false], authored: null })
  global.agent = ag
  r = await sr.producePhase('plan', 'wi')
  assert.strictEqual(r.confidence, 'low', 'failed produce -> low (park)')

  // (d) authored but still not usable -> low confidence (UFR-4).
  ag = agentWith({ usableSeq: [false, false], authored: { status: 'ok' } })
  global.agent = ag
  r = await sr.producePhase('plan', 'wi')
  assert.strictEqual(r.confidence, 'low', 'authored-but-not-usable -> low (park)')

  // (e) produce returns a NOTIFY default + ledger write ok -> high (NOTIFY durably recorded).
  ag = agentWith({ usableSeq: [false, true], authored: { status: 'ok', notify: [{ identity: 'n1', message: 'went with X' }] } })
  global.agent = ag
  r = await sr.producePhase('plan', 'wi')
  assert.strictEqual(r.confidence, 'high', 'authored + notify recorded + usable -> high')

  // (f) NOTIFY default but the durable ledger write fails -> low (UFR-2: not silently lost).
  ag = agentWith({ usableSeq: [false], authored: { status: 'ok', notify: [{ identity: 'n1', message: 'went with X' }] }, notifyOk: false })
  global.agent = ag
  r = await sr.producePhase('plan', 'wi')
  assert.strictEqual(r.confidence, 'low', 'failed NOTIFY durable write -> low (park, UFR-2)')
  // (g) FR-5: producePhase embeds selfContained() write-marker command in the author agent prompt
  // when __SR_ROOT is set. The embedded command must be cd-prefixed so the haiku leaf uses the correct repo.
  const savedRoot = globalThis.__SR_ROOT
  try {
    globalThis.__SR_ROOT = '/test-repo'
    let capturedPrompt = null
    const agG = async (prompt, opts) => {
      const label = (opts && opts.label) || ''
      if (label === 'exec') {
        if (prompt.includes('emit-signals')) return [{ index: 0, ok: true, stdout: NOT_USABLE_SIGNAL }]
        if (prompt.includes('append-notify')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
        return [{ index: 0, ok: true, stdout: '' }, { index: 1, ok: true, stdout: '' }]
      }
      if (label === 'exec2') return [{ index: 0, ok: true, stdout: USABLE_SIGNAL }]
      if (label.startsWith('produce-')) {
        capturedPrompt = prompt
        return { status: 'ok' }
      }
      return null
    }
    // Override exec emit-signals to return not-usable first, then usable on second call.
    let emitCount = 0
    global.agent = async (prompt, opts) => {
      const label = (opts && opts.label) || ''
      if (label === 'exec') {
        if (prompt.includes('emit-signals')) {
          emitCount += 1
          return [{ index: 0, ok: true, stdout: emitCount === 1 ? NOT_USABLE_SIGNAL : USABLE_SIGNAL }]
        }
        if (prompt.includes('append-notify')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
        return [{ index: 0, ok: true, stdout: '' }, { index: 1, ok: true, stdout: '' }]
      }
      if (label.startsWith('produce-')) { capturedPrompt = prompt; return { status: 'ok' } }
      return null
    }
    emitCount = 0
    await sr.producePhase('plan', 'wi-fr5')
    assert.ok(capturedPrompt !== null, 'produce leaf was called')
    assert.ok(capturedPrompt.includes("cd '/test-repo' && python3 plugins/superheroes/lib/front_half_usable.py"),
      'producePhase embeds selfContained write-marker command when __SR_ROOT is set')
  } finally {
    globalThis.__SR_ROOT = savedRoot
  }

  console.log('ok: producePhase resume / re-produce / park / notify (exec+twin, no cmdRunner) + FR-5 cd-prefix in embedded write-marker')
}
main().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
