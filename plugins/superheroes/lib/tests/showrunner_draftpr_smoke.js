// plugins/superheroes/lib/tests/showrunner_draftpr_smoke.js
// #115 Task 16: draftPRPhase twin-not-agent boundary smoke.
// Pins that adopt/create/gate judgment is the in-process JS twin (recoverTwin.prAction)
// over an exec world-read, NOT a cmdRunner decision agent dispatching pr_entry.py --step draft.
//
// The THROW on unexpected agent route means a mutant reverting to the old cmdRunner path
// immediately fails — no implicit pass for unrouted calls.
const assert = require('assert')

function makeStubs({ worldPayload, createPayload }) {
  global.log = () => {}

  global.agent = async (p, opts) => {
    const label = (opts && opts.label) || ''
    // WORLD-READ path: exec label, --emit-world flag — allowed, returns worldPayload.
    if (label === 'exec' && p.includes('--emit-world')) {
      const stdout = worldPayload === null ? JSON.stringify({ pr: null }) : JSON.stringify(worldPayload)
      return [{ index: 0, ok: true, stdout }]
    }
    // CREATE path: exec label, pr_entry.py --step draft WITHOUT --emit-world.
    if (label === 'exec' && p.includes('pr_entry.py') && p.includes('--step draft') && !p.includes('--emit-world')) {
      if (createPayload === undefined) {
        throw new Error('unexpected create exec: should not reach create path for this case')
      }
      return [{ index: 0, ok: true, stdout: JSON.stringify(createPayload) }]
    }
    // OLD DECISION-AGENT PATH: if anyone dispatches pr_entry.py --step draft as a cmdRunner
    // (lib-label) decision call (the pre-#115 pattern), throw — that is the regression we pin.
    if (label === 'lib' && p.includes('pr_entry.py') && p.includes('--step draft')) {
      throw new Error(
        'REGRESSION: draftPRPhase dispatched pr_entry.py --step draft as a decision agent (label:lib). ' +
        'It must use exec (label:exec) + in-process recoverTwin.prAction instead.'
      )
    }
    throw new Error('unexpected agent: label=' + label + ' prompt=' + p.slice(0, 80))
  }

  delete require.cache[require.resolve('../showrunner.js')]
  return require('../showrunner.js')
}

;(async () => {
  // ── Case 1: ADOPT ────────────────────────────────────────────────────────────
  // world-read returns an open PR with a number → prAction returns 'adopt'
  // → sideEffect carries the PR object, confidence high; no create exec.
  {
    const pr = { number: 7, url: 'https://github.com/x/y/pull/7', state: 'open' }
    const sr = makeStubs({ worldPayload: { pr }, createPayload: undefined /* must not be called */ })
    const out = await sr.draftPRPhase('my-work-item')
    assert.strictEqual(out.phaseResult.confidence, 'high', 'adopt: confidence high')
    assert.deepStrictEqual(out.sideEffect, { pr }, 'adopt: sideEffect carries the open PR')
  }

  // ── Case 2: CREATE ───────────────────────────────────────────────────────────
  // world-read returns {pr:null} → prAction returns 'create'
  // → create exec runs and returns a new PR → sideEffect carries the new PR.
  {
    let createExecHit = false
    const newPr = { number: 8, url: 'https://github.com/x/y/pull/8', state: 'open' }
    // Wrap makeStubs with a sentinel to confirm the create path was actually taken.
    global.log = () => {}
    global.agent = async (p, opts) => {
      const label = (opts && opts.label) || ''
      if (label === 'exec' && p.includes('--emit-world')) {
        return [{ index: 0, ok: true, stdout: JSON.stringify({ pr: null }) }]
      }
      if (label === 'exec' && p.includes('pr_entry.py') && p.includes('--step draft') && !p.includes('--emit-world')) {
        createExecHit = true
        return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true, pr: newPr }) }]
      }
      if (label === 'lib' && p.includes('pr_entry.py') && p.includes('--step draft')) {
        throw new Error('REGRESSION: decision agent dispatched for draft-PR (must be exec twin)')
      }
      throw new Error('unexpected agent: label=' + label + ' prompt=' + p.slice(0, 80))
    }
    delete require.cache[require.resolve('../showrunner.js')]
    const sr = require('../showrunner.js')
    const out = await sr.draftPRPhase('my-work-item')
    assert.ok(createExecHit, 'create: the create exec path was taken')
    assert.strictEqual(out.phaseResult.confidence, 'high', 'create: confidence high')
    assert.deepStrictEqual(out.sideEffect, { pr: newPr }, 'create: sideEffect carries new PR')
  }

  // ── Case 3: GATE (transient / unknown) ───────────────────────────────────────
  // world-read returns {pr:'unknown'} → prAction returns 'gate' → sideEffect null,
  // confidence low. Pins fail-closed: no 2nd PR is created.
  {
    const sr = makeStubs({ worldPayload: { pr: 'unknown' }, createPayload: undefined })
    const out = await sr.draftPRPhase('my-work-item')
    assert.strictEqual(out.phaseResult.confidence, 'low', 'gate: confidence low (parked)')
    assert.strictEqual(out.sideEffect, null, 'gate: sideEffect null (no 2nd PR)')
  }

  // ── Case 4: GATE (dropped pr key — fail-CLOSED) ──────────────────────────────
  // The cheap leaf summarized the world to valid-JSON {} (the top-level `pr` key dropped).
  // JSON.parse SUCCEEDS, so the old code overwrote the sentinel → world={} → world.pr undefined
  // → prAction fell through to 'create' → a DUPLICATE draft PR. The fix re-arms the
  // { pr: 'unknown' } sentinel when the parsed object has no own `pr` key → routes to GATE.
  // makeStubs is constructed with createPayload:undefined, so the create exec THROWS if reached —
  // this case FAILS pre-fix (it would create) and passes post-fix (it gates).
  {
    const sr = makeStubs({ worldPayload: {} /* valid JSON, no pr key */, createPayload: undefined })
    const out = await sr.draftPRPhase('my-work-item')
    assert.strictEqual(out.phaseResult.confidence, 'low', 'dropped-pr: confidence low (gated, not created)')
    assert.strictEqual(out.sideEffect, null, 'dropped-pr: sideEffect null (no 2nd PR)')
  }

  console.log('OK: draftPRPhase twin-boundary: adopt->high+pr, create->high+newPR(exec-hit), gate->low+null, dropped-pr->gate(no 2nd PR)')
})().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
