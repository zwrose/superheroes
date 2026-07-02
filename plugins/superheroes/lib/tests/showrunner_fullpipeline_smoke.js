// plugins/superheroes/lib/tests/showrunner_fullpipeline_smoke.js
// #115 Task 12: phaseStep is the JS twin (in-process). #118: the per-phase tail (journal +
// cursor + side effect) is ONE 'save phase progress' courier; the ship-entry PR read is the
// exec courier (checkpoint_entry --read-pr). ship-phase IO is folded into courier leaves.
const assert = require('assert')
const PR = { number: 1, url: 'https://github.com/o/r/pull/1', isDraft: true }

function jsonOut(obj) { return [{ ok: true, stdout: JSON.stringify(obj) }] }

global.log = () => {}
global.agent = async (p, opts) => {
  const label = (opts && opts.label) || ''
  if (label === 'resolve review target') {
    return jsonOut({ ok: true, worktree: '/wt', expectedHead: '/wt-head-sha' })
  }
  if (label === 'check ship-readiness') {
    return jsonOut({
      ok: true,
      reconcile: { ok: true, head: '/wt-head-sha', reason: 'in sync' },
      freshness: { decision: 'up_to_date' },
      integrated: false,
      checks: [{ name: 'ci', bucket: 'pass', state: 'success' }],
    })
  }
  if (label === 'post readout') return jsonOut({ posted: true, recorded: true })
  if (label === 'save phase progress') {
    if (p.includes('journal_entry') || p.includes('checkpoint_entry')) {
      throw new Error('phase tail must ride phase_progress_entry.py save, not journal_entry/checkpoint_entry')
    }
    return JSON.stringify({ ok: true, journal_confirmed: true, checkpoint_confirmed: true })
  }
  if (label === 'exec') {
    if (p.includes('emit-checks')) {
      return [{ index: 0, ok: true, stdout: JSON.stringify([{ name: 'ci', bucket: 'pass', state: 'success' }]) }]
    }
    if (p.includes('checkpoint_entry') && p.includes('--read-pr')) return JSON.stringify({ pr: PR })
    if (p.includes('fence_cli')) return JSON.stringify({ ok: true })
    return [{ index: 0, ok: true, stdout: '' }, { index: 1, ok: true, stdout: '' }]
  }
  if (label === 'lib') {
    if (p.includes('phase_step_cli')) throw new Error('phase_step_cli dispatched as agent — must use JS twin')
    if (p.includes('journal_entry') || p.includes('checkpoint_entry')) {
      throw new Error('journal_entry/checkpoint_entry must not ride separate cmdRunner leaves (#118 tail)')
    }
    return { ok: true }
  }
  throw new Error('unexpected agent: label=' + label + ' ' + p.slice(0, 50))
}
const sr = require('../showrunner.js')
;(async () => {
  const ok = { confidence: 'high', assumptions: [] }
  const deps = {
    produce: async () => ok,
    reviewDoc: async () => ({ phaseResult: ok, gate: 'passed' }),
    build: async () => ok,
    reviewCode: async () => ({ phaseResult: ok, gate: 'passed' }),
    draftPR: async () => ({ phaseResult: ok, sideEffect: { pr: PR } }),
    testPilot: async () => ok,
    markReady: async () => ({ phaseResult: ok, sideEffect: { ready: true } }),
    gateRead: async () => null,
    generation: 5,
  }
  const out = await sr.runPhases('wi', 0, deps)
  assert.strictEqual(out.outcome, 'ready', 'full pipeline must reach a ready-for-review outcome')
  assert.strictEqual(out.phase, 'ship')
  console.log('OK: full pipeline reaches a ready-for-review outcome (phaseStep is JS twin)')
})().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
