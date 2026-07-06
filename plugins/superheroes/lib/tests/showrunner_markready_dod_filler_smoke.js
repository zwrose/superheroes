// mark-ready DoD filler leg (issue #228 "build/ship legs fill it" — found missing live in
// the 0.10.0 qualification): a gate park with the machine field gate === 'dod' dispatches
// exactly ONE fill-dod model leaf and re-decides once; a park WITHOUT that field (or a
// filler failure) never dispatches/loops; a clean gate never dispatches the filler at all.
const assert = require('assert')

function freshShowrunner() {
  delete require.cache[require.resolve('../showrunner.js')]
  return require('../showrunner.js')
}

async function scenarioFilledAndFlipped() {
  const labels = []
  let gateCalls = 0
  global.log = () => {}
  global.agent = async (_prompt, opts) => {
    const label = opts && opts.label
    labels.push(label)
    if (label === 'mark PR ready') {
      gateCalls += 1
      if (gateCalls === 1) {
        return [{ ok: true, stdout: JSON.stringify({ ok: false, read_back: false, gate: 'dod', pr: 77, reason: 'DoD gate: bullet X — no disposition (expected done or deferred)' }) }]
      }
      return [{ ok: true, stdout: JSON.stringify({ ok: true, read_back: true }) }]
    }
    if (label === 'fill-dod') {
      assert.ok(String(_prompt).includes('#77'), 'filler prompt must carry the PR number')
      assert.ok(String(_prompt).includes('LEAVE THE ROW BLANK'), 'filler prompt must carry the honesty contract')
      return { ok: true, filled: 3, blank: 0 }
    }
    throw new Error(`unexpected label ${label || 'none'}`)
  }
  const sr = freshShowrunner()
  const out = await sr.markReadyPhase('wi-dod')
  assert.strictEqual(out.phaseResult.confidence, 'high')
  assert.deepStrictEqual(out.sideEffect, { ready: true })
  assert.deepStrictEqual(labels, ['mark PR ready', 'fill-dod', 'mark PR ready'])
  console.log('ok: dod park -> one filler leaf -> one re-decide -> ready')
}

async function scenarioStillBlankParks() {
  const labels = []
  global.log = () => {}
  global.agent = async (_prompt, opts) => {
    const label = opts && opts.label
    labels.push(label)
    if (label === 'mark PR ready') {
      return [{ ok: true, stdout: JSON.stringify({ ok: false, read_back: false, gate: 'dod', pr: 77, reason: 'DoD gate: bullet X — no disposition (expected done or deferred)' }) }]
    }
    if (label === 'fill-dod') return { ok: true, filled: 2, blank: 1 }
    throw new Error(`unexpected label ${label || 'none'}`)
  }
  const sr = freshShowrunner()
  const out = await sr.markReadyPhase('wi-dod')
  // gate parked again on the still-blank row: exactly one filler, exactly two gate runs, honest park.
  assert.strictEqual(out.phaseResult.confidence, 'low')
  assert.strictEqual(out.sideEffect, null)
  assert.deepStrictEqual(labels, ['mark PR ready', 'fill-dod', 'mark PR ready'])
  assert.ok(out.phaseResult.assumptions[0].includes('DoD gate'), 'park keeps the gate reason')
  console.log('ok: still-blank row -> single retry -> honest park (no loop)')
}

async function scenarioNonDodParkNoFiller() {
  const labels = []
  global.log = () => {}
  global.agent = async (_prompt, opts) => {
    const label = opts && opts.label
    labels.push(label)
    if (label === 'mark PR ready') {
      return [{ ok: true, stdout: JSON.stringify({ ok: false, read_back: false, reason: 'PR isDraft unreadable — not flipping blind' }) }]
    }
    throw new Error(`unexpected label ${label || 'none'}`)
  }
  const sr = freshShowrunner()
  const out = await sr.markReadyPhase('wi-plain')
  assert.strictEqual(out.phaseResult.confidence, 'low')
  assert.deepStrictEqual(labels, ['mark PR ready'])
  console.log('ok: non-dod park never dispatches the filler')
}

async function scenarioFillerFailureKeepsPark() {
  const labels = []
  global.log = () => {}
  global.agent = async (_prompt, opts) => {
    const label = opts && opts.label
    labels.push(label)
    if (label === 'mark PR ready') {
      return [{ ok: true, stdout: JSON.stringify({ ok: false, read_back: false, gate: 'dod', pr: 77, reason: 'DoD gate: bullet X — no disposition (expected done or deferred)' }) }]
    }
    if (label === 'fill-dod') throw new Error('filler leaf crashed')
    throw new Error(`unexpected label ${label || 'none'}`)
  }
  const sr = freshShowrunner()
  const out = await sr.markReadyPhase('wi-dod')
  // filler crash -> no gate re-run, the original honest park stands.
  assert.strictEqual(out.phaseResult.confidence, 'low')
  assert.deepStrictEqual(labels, ['mark PR ready', 'fill-dod'])
  console.log('ok: filler failure -> original park stands, no re-decide')
}

;(async () => {
  await scenarioFilledAndFlipped()
  await scenarioStillBlankParks()
  await scenarioNonDodParkNoFiller()
  await scenarioFillerFailureKeepsPark()
})().catch((e) => { console.error('FAIL:', e.message || e); process.exit(1) })
