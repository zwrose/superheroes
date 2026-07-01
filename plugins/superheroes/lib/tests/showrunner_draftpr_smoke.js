// plugins/superheroes/lib/tests/showrunner_draftpr_smoke.js
// Task 8: draft-PR is one folded courier leaf with read-back confirmation.
const assert = require('assert')

function makeStubs(outPayload) {
  const labels = []
  global.log = () => {}
  global.agent = async (_prompt, opts) => {
    labels.push(opts && opts.label)
    if ((opts && opts.label) === 'open draft PR') {
      return [{ ok: true, stdout: JSON.stringify(outPayload) }]
    }
    throw new Error(`unexpected label ${(opts && opts.label) || 'none'}`)
  }
  delete require.cache[require.resolve('../showrunner.js')]
  return { sr: require('../showrunner.js'), labels }
}

;(async () => {
  {
    const pr = { number: 8, url: 'https://github.com/x/y/pull/8', state: 'open' }
    const { sr, labels } = makeStubs({ ok: true, pr, read_back: true })
    const out = await sr.draftPRPhase('my-work-item')
    assert.strictEqual(out.phaseResult.confidence, 'high', 'create: confidence high')
    assert.deepStrictEqual(out.sideEffect, { pr }, 'create: sideEffect carries the PR')
    assert.deepStrictEqual(labels, ['open draft PR'])
  }

  {
    const pr = { number: 7, url: 'https://github.com/x/y/pull/7', state: 'open' }
    const { sr } = makeStubs({ ok: true, pr, read_back: false, reason: 'read-back mismatch' })
    const out = await sr.draftPRPhase('my-work-item')
    assert.strictEqual(out.phaseResult.confidence, 'low', 'read-back fail: confidence low')
    assert.strictEqual(out.sideEffect, null, 'read-back fail: sideEffect null')
  }

  {
    const { sr } = makeStubs({ ok: false, reason: 'gh unavailable' })
    const out = await sr.draftPRPhase('my-work-item')
    assert.strictEqual(out.phaseResult.confidence, 'low', 'create fail: confidence low')
    assert.strictEqual(out.sideEffect, null, 'create fail: sideEffect null')
  }

  {
    const { sr } = makeStubs({ ok: true, read_back: true })
    const out = await sr.draftPRPhase('my-work-item')
    assert.strictEqual(out.phaseResult.confidence, 'low', 'missing pr: confidence low (gated)')
    assert.strictEqual(out.sideEffect, null, 'missing pr: sideEffect null (no 2nd PR)')
  }

  {
    const { sr } = makeStubs({ ok: true, pr: null, read_back: true })
    const out = await sr.draftPRPhase('my-work-item')
    assert.strictEqual(out.phaseResult.confidence, 'low', 'null pr: confidence low (gated)')
    assert.strictEqual(out.sideEffect, null, 'null pr: sideEffect null (no 2nd PR)')
  }

  console.log('OK: draftPRPhase folded read-back: create->high+pr, read-back-fail->low+null, create-fail->low+null, missing-pr->gate')
})().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
