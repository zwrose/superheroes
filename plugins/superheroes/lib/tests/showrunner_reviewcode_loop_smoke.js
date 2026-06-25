// plugins/superheroes/lib/tests/showrunner_reviewcode_loop_smoke.js
// Dev-time (node, not CI): drives the REAL reviewPanel shell with reviewCodePhase's real wrappers
// across every terminal + the UFR-2 covers-stamp-failure park. Stubs the Workflow runtime + the
// lib command-runner. Run: node plugins/superheroes/lib/tests/showrunner_reviewcode_loop_smoke.js
const assert = require('assert')
const sr = require('../showrunner.js')

global.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))
global.log = () => {}

// A scenario supplies the tally terminal(s) — a single string, or a queue for a multi-round run
// (the last value repeats) — and whether the covers-stamp write succeeds.
function install({ terminal, provOk = true }) {
  const queue = Array.isArray(terminal) ? terminal.slice() : [terminal]
  const nextTerminal = () => (queue.length > 1 ? queue.shift() : queue[0])
  const calls = { prov: 0, readout: 0, readoutPost: 0, fix: 0, recordDeferred: 0 }
  global.agent = async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    // mimic the real reviewers/leaves creating round-<N>/ (where the shell writes synthesized.json).
    const m = prompt && prompt.match(/(\/tmp\/[^\s'"]*\/round-\d+)/)
    if (m) { try { require('fs').mkdirSync(m[1], { recursive: true }) } catch (_) {} }
    if (label === 'resume') return '1'
    if (label.startsWith('tally')) {
      const t = nextTerminal()
      return { schemaVersion: 1, terminal: t, gate: t === 'clean' ? 'clean' : 'blocking', reason: t, findings: [] }
    }
    if (label.startsWith('verify')) return { result: 'pass' }
    if (label.startsWith('synthesis')) return { findings: [], drops: [] }
    if (label === 'code-fixer') { calls.fix += 1; return { fixed: ['fixed a.py'], deferred: [{ id: 'a.py::bug', severity: 'Important', parentOrigin: 'plan' }] } }
    if (label === 'readout') { calls.readout += 1; return '## Review loop — done' }
    if (label === 'lib') {
      if (prompt.includes('review_code_config.py')) return { verifyCommand: 'none', tiers: { reviewer: 'sonnet', reviewerDeep: 'opus', synthesis: 'opus', fixer: 'sonnet' } }
      if (prompt.includes('prov_entry.py')) { calls.prov += 1; return { ok: provOk, error: provOk ? undefined : 'disk full' } }
      if (prompt.includes('readout_post.py')) { calls.readoutPost += 1; return { posted: false, recorded: true } }
      if (prompt.includes('record_deferred.py')) { calls.recordDeferred += 1; return { ok: true } }
      return { ok: true }
    }
    return null   // reviewer / merge leaves "complete"
  }
  return calls
}

async function main() {
  // 1. clean -> advance + covers stamped (FR-9), gate passed.
  let calls = install({ terminal: 'clean' })
  let r = await sr.reviewCodePhase('wi-clean')
  assert.strictEqual(r.gate, 'passed', 'clean -> passed')
  assert.strictEqual(calls.prov, 1, 'clean stamps covers exactly once')

  // 2. clean-with-skips -> advance, gate passed, NO covers stamp (parks later at the ship gate).
  calls = install({ terminal: 'clean-with-skips' })
  r = await sr.reviewCodePhase('wi-skips')
  assert.strictEqual(r.gate, 'passed', 'clean-with-skips advances like clean')
  assert.strictEqual(calls.prov, 0, 'clean-with-skips records NO covers stamp')

  // 3. halted -> park (changes-requested) + readout posted (names parentOrigin) (UFR-1).
  calls = install({ terminal: 'halted' })
  r = await sr.reviewCodePhase('wi-halt')
  assert.strictEqual(r.gate, 'changes-requested', 'halted -> park')
  assert.ok(calls.readout === 1 && calls.readoutPost === 1, 'halted posts the uniform readout')
  assert.strictEqual(calls.prov, 0, 'a park never stamps covers')

  // 4. cannot-certify -> park (changes-requested).
  calls = install({ terminal: 'cannot-certify' })
  r = await sr.reviewCodePhase('wi-cc')
  assert.strictEqual(r.gate, 'changes-requested', 'cannot-certify -> park')

  // 5. UFR-2: clean but the covers-stamp write fails -> low-confidence park, NOT ship-ready.
  calls = install({ terminal: 'clean', provOk: false })
  r = await sr.reviewCodePhase('wi-ufr2')
  assert.strictEqual(r.gate, 'changes-requested', 'failed covers stamp -> park, never ship-ready (UFR-2)')
  assert.strictEqual(r.phaseResult.confidence, 'low', 'UFR-2 park is low-confidence (resumable)')

  // 6. continue -> fix step + recordDeferred -> re-tally clean (the fix path is wired, loop converges).
  calls = install({ terminal: ['continue', 'clean'] })
  r = await sr.reviewCodePhase('wi-fix')
  assert.strictEqual(r.gate, 'passed', 'continue then clean converges to passed')
  assert.ok(calls.fix === 1 && calls.recordDeferred === 1, 'the fix step + recordDeferred leaves are invoked')
  assert.strictEqual(calls.prov, 1, 'a fix-applied clean still stamps covers (X′)')

  console.log('ok: reviewCodePhase clean/skips/halted/cannot-certify + UFR-2 + continue/fix/clean')
}

main().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
