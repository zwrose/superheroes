// plugins/superheroes/lib/tests/showrunner_draftpr_smoke.js
// Task 8: draft-PR is one folded courier leaf with read-back confirmation.
// #219 (Task 5): the phase now composes a durable "what & why" PR body first — a Python `context`
// courier ('pr-body context') that also answers prior_body_usable, then (only when no usable prior
// body) a Sonnet 'compose PR body' leaf whose prose is written to a durable file and threaded to
// pr_entry via --body-file. A compose failure returns null (pr_entry falls back deterministically),
// never blocking the phase. The reuse probe lives Python-side, so the spine io()-reads nothing here.
const assert = require('assert')

// makeStubs(outPayload, opts): global.agent answers by label. opts.priorBody -> the context courier
// reports the durable body is reusable (resume-cheap: no 'compose PR body' dispatch). opts.composeReply
// overrides the Sonnet leaf's answer (e.g. {} to simulate an empty/failed compose). io is writes-only.
function makeStubs(outPayload, opts) {
  opts = opts || {}
  const labels = []
  let draftCmd = null
  global.log = () => {}
  // Writes-only io seam (there is NO read in this design — the reuse probe is Python-side); mirrors
  // showrunner_io_seam_smoke.js. readJson returns its default so nothing depends on a real read.
  global.io = { async writeFile() {}, async readJson(_p, d) { return d } }
  global.agent = async (prompt, o) => {
    const label = o && o.label
    labels.push(label)
    if (label === 'pr-body context') {
      // courier-shaped stdout: the context gather (+ prior_body_usable). Rides execJson/runCourierJson.
      const ctx = { work_item: 'wi', commits: [], prior_body_usable: !!opts.priorBody }
      return [{ ok: true, stdout: JSON.stringify(ctx) }]
    }
    if (label === 'compose PR body') {
      // genuine Sonnet leaf: return the typed {body} object (or the case's override, e.g. {} = no body).
      return ('composeReply' in opts) ? opts.composeReply : { body: 'A composed body.\n\nCloses #219' }
    }
    if (label === 'open draft PR') {
      draftCmd = String(prompt)
      return [{ ok: true, stdout: JSON.stringify(outPayload) }]
    }
    throw new Error(`unexpected label ${label || 'none'}`)
  }
  delete require.cache[require.resolve('../showrunner.js')]
  return { sr: require('../showrunner.js'), labels, draftCmd: () => draftCmd }
}

;(async () => {
  // create case: the Sonnet body is composed and reaches pr_entry via --body-file.
  {
    const pr = { number: 8, url: 'https://github.com/x/y/pull/8', state: 'open' }
    const { sr, labels, draftCmd } = makeStubs({ ok: true, pr, read_back: true })
    const out = await sr.draftPRPhase('my-work-item')
    assert.strictEqual(out.phaseResult.confidence, 'high', 'create: confidence high')
    assert.deepStrictEqual(out.sideEffect, { pr }, 'create: sideEffect carries the PR')
    assert.ok(labels.includes('compose PR body'), 'create: the Sonnet compose leaf fired')
    assert.ok(labels.includes('pr-body context'), 'create: the context courier fired')
    assert.ok(/--body-file /.test(draftCmd()), 'create: the composed prose reaches pr_entry via --body-file')
    delete global.io
  }

  // resume-reuse case: a usable prior body -> NO Sonnet re-spend, but the durable path is still passed.
  {
    const pr = { number: 8, url: 'https://github.com/x/y/pull/8', state: 'open' }
    const { sr, labels, draftCmd } = makeStubs({ ok: true, pr, read_back: true }, { priorBody: true })
    const out = await sr.draftPRPhase('my-work-item')
    assert.strictEqual(out.phaseResult.confidence, 'high', 'resume: confidence high')
    assert.ok(!labels.includes('compose PR body'), 'resume: no Sonnet re-spend when a prior body is usable')
    assert.ok(labels.includes('pr-body context'), 'resume: the context courier still fired')
    assert.ok(/--body-file /.test(draftCmd()), 'resume: the durable body path still reaches pr_entry')
    delete global.io
  }

  // compose-failure case: the Sonnet leaf returns no body -> null path -> NO --body-file (pr_entry
  // falls back deterministically), and the phase STILL succeeds (compose is never a ship blocker).
  {
    const pr = { number: 8, url: 'https://github.com/x/y/pull/8', state: 'open' }
    const { sr, labels, draftCmd } = makeStubs({ ok: true, pr, read_back: true }, { composeReply: {} })
    const out = await sr.draftPRPhase('my-work-item')
    assert.strictEqual(out.phaseResult.confidence, 'high', 'compose-fail: phase still succeeds')
    assert.deepStrictEqual(out.sideEffect, { pr }, 'compose-fail: sideEffect carries the PR')
    assert.ok(labels.includes('compose PR body'), 'compose-fail: the compose leaf was attempted')
    assert.ok(!/--body-file /.test(draftCmd()), 'compose-fail: no --body-file (deterministic fallback in pr_entry)')
    delete global.io
  }

  // read-back fail: the folded leaf reports read_back:false -> gate low, no PR side effect.
  {
    const pr = { number: 7, url: 'https://github.com/x/y/pull/7', state: 'open' }
    const { sr } = makeStubs({ ok: true, pr, read_back: false, reason: 'read-back mismatch' })
    const out = await sr.draftPRPhase('my-work-item')
    assert.strictEqual(out.phaseResult.confidence, 'low', 'read-back fail: confidence low')
    assert.strictEqual(out.sideEffect, null, 'read-back fail: sideEffect null')
    delete global.io
  }

  // create fail: ok:false -> gate low, no PR side effect.
  {
    const { sr } = makeStubs({ ok: false, reason: 'gh unavailable' })
    const out = await sr.draftPRPhase('my-work-item')
    assert.strictEqual(out.phaseResult.confidence, 'low', 'create fail: confidence low')
    assert.strictEqual(out.sideEffect, null, 'create fail: sideEffect null')
    delete global.io
  }

  // missing pr: ok+read_back but no pr -> gate low (never a 2nd PR).
  {
    const { sr } = makeStubs({ ok: true, read_back: true })
    const out = await sr.draftPRPhase('my-work-item')
    assert.strictEqual(out.phaseResult.confidence, 'low', 'missing pr: confidence low (gated)')
    assert.strictEqual(out.sideEffect, null, 'missing pr: sideEffect null (no 2nd PR)')
    delete global.io
  }

  // null pr: explicit pr:null -> gate low (never a 2nd PR).
  {
    const { sr } = makeStubs({ ok: true, pr: null, read_back: true })
    const out = await sr.draftPRPhase('my-work-item')
    assert.strictEqual(out.phaseResult.confidence, 'low', 'null pr: confidence low (gated)')
    assert.strictEqual(out.sideEffect, null, 'null pr: sideEffect null (no 2nd PR)')
    delete global.io
  }

  console.log('OK: draftPRPhase #219 body-compose: create->compose+--body-file, resume-reuse->no re-spend, ' +
    'compose-fail->deterministic fallback (no --body-file); read-back/create-fail/missing-pr gating intact')
})().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
