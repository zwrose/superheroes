// Smoke: runPhases routes the four front-half phases to the injected deps and PARKS at the front-half
// boundary after review-tasks (does not begin build); switch-off routes the unchanged defaultPhaseLeaf
// path and reaches build (FR-9).
// #115 Task 12: phaseStep is now the JS twin (in-process). #118: the per-phase tail rides ONE
// 'save phase progress' courier — journal_entry/checkpoint_entry never ride separate leaves.
const assert = require('assert')
const sr = require('../showrunner.js')

global.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))
global.log = () => {}
global.agent = async (prompt, opts) => {
  const label = (opts && opts.label) || ''
  if (label === 'save phase progress') {
    return JSON.stringify({ ok: true, journal_confirmed: true, checkpoint_confirmed: true })
  }
  if (label === 'exec') {
    // exec batches; return ok for any batch
    return [{ index: 0, ok: true, stdout: '' }, { index: 1, ok: true, stdout: '' }]
  }
  if (label === 'lib') {
    if (prompt.includes('journal_entry') || prompt.includes('checkpoint_entry')) {
      throw new Error('journal_entry/checkpoint_entry must not ride separate cmdRunner leaves (#118 tail)')
    }
    // phase_step_cli.py must NOT be dispatched as an agent (it is now the in-process JS twin).
    if (prompt.includes('phase_step_cli')) throw new Error('phase_step_cli dispatched as agent — must use JS twin instead')
    return { ok: true }
  }
  return null
}

async function main() {
  // (a) front-half deps present: route produce/reviewDoc, then park at the boundary; build NOT reached.
  const seen = []
  const deps = {
    produce: async (phase) => { seen.push('produce:' + phase); return { confidence: 'high', assumptions: [] } },
    reviewDoc: async (doc) => { seen.push('reviewDoc:' + doc); return { phaseResult: { confidence: 'high', assumptions: [] }, gate: 'passed' } },
    frontHalfBoundary: async () => ({ outcome: 'parked', phase: 'front-half-boundary', reason: 'boundary' }),
    build: async () => { seen.push('build'); return { confidence: 'high', assumptions: [] } },
  }
  const result = await sr.runPhases('wi', 0, deps)
  assert.strictEqual(result.phase, 'front-half-boundary', 'parks at the front-half boundary (FR-7)')
  assert.deepStrictEqual(seen,
    ['produce:plan', 'reviewDoc:plan', 'produce:tasks', 'reviewDoc:tasks'],
    'front-half routed in order; build NOT reached')

  // (b) deps absent (switch off): the front-half phases use the unchanged defaultPhaseLeaf, reaching build.
  const seen2 = []
  const depsOff = { build: async () => { throw new Error('STOP') },
    phaseLeaf: async (phase) => { seen2.push('leaf:' + phase); return { confidence: 'high', assumptions: [] } },
    gateRead: async () => 'passed' }
  try { await sr.runPhases('wi', 0, depsOff) } catch (_) {}
  assert.deepStrictEqual(seen2, ['leaf:plan', 'leaf:review-plan', 'leaf:tasks', 'leaf:review-tasks'],
    'switch-off path runs the unchanged defaultPhaseLeaf for every front-half phase')

  // (c) RESUME into the back-half (fromStep=4=build) with the front-half on: parks at the boundary,
  // never builds — the boundary guard sits at the build phase, so it is resume-safe (FR-7).
  const seenR = []
  const depsR = {
    frontHalfBoundary: async () => ({ outcome: 'parked', phase: 'front-half-boundary', reason: 'boundary' }),
    build: async () => { seenR.push('build'); return { confidence: 'high', assumptions: [] } },
  }
  const rr = await sr.runPhases('wi', 4, depsR)
  assert.strictEqual(rr.phase, 'front-half-boundary', 'resume into build parks at the boundary (FR-7)')
  assert.deepStrictEqual(seenR, [], 'build is NOT reached on a resume into the back-half')
  console.log('ok: front-half switch + runPhases branches + boundary park (incl. resume)')
}

main().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
