// Smoke: producePhase resumes a usable draft (no authoring), re-produces when not usable, and parks
// (low confidence) when the produce leaf fails or yields no usable draft. Stubs the leaves.
const assert = require('assert')
const sr = require('../showrunner.js')
global.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))
global.log = () => {}

function agentWith({ usableSeq, authored, notifyOk = true }) {
  const seq = usableSeq.slice()
  let produceCalls = 0
  const fn = async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    if (label === 'lib') {
      if (prompt.includes('front_half_usable.py') && prompt.includes('--write-marker')) return { wrote: true }
      if (prompt.includes('front_half_usable.py')) return { usable: seq.shift() }   // usableDraft check
      if (prompt.includes('append-notify')) return { ok: notifyOk }
      if (prompt.includes('model_tier_resolve')) return { model: 'opus' }
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

  // (b) not usable -> author -> stamp -> re-check usable -> high.
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
  console.log('ok: producePhase resume / re-produce / park / notify')
}
main().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
