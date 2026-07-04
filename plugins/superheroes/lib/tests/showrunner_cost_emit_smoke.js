// #130: the spine folds phase_cost telemetry into the ONE per-phase 'save phase progress' leaf (no
// new courier leaf — #118). persistPhase({recordCost:true}) threads --cost-payload carrying the
// captured proxy dispatch counts + the budget-measured output-token delta; without recordCost, or for
// an empty phase (no dispatches, unmeasured), no cost payload rides — back-compat for other callers.
const assert = require('assert')
const showrunner = require('../showrunner.js')
const cm = require('../cost_meter.js')

;(async () => {
  global.log = () => {}
  const seen = []
  global.agent = async (prompt, opts) => {
    seen.push({ prompt, label: opts && opts.label })
    return [{ ok: true, stdout: JSON.stringify({ ok: true, journal_confirmed: true, checkpoint_confirmed: true }) }]
  }

  // recordCost folds --cost-payload into the ONE save leaf
  cm.reset()
  let spent = 2000
  globalThis.__SR_BUDGET = { spent: () => spent }
  globalThis.__SR_PHASE = 'workhorse'
  cm.mark('workhorse')
  cm.record('claude-opus-4-8'); cm.record('claude-haiku-4-5-20251001')
  spent = 2500
  const res = await showrunner.persistPhase('wi', {
    step: 4, phase: 'workhorse', record: { phase: 'workhorse', confidence: 'high' }, recordCost: true })
  assert.strictEqual(res.ok, true)
  assert.strictEqual(seen.length, 1, 'exactly ONE leaf — cost rides the save, no separate cost leaf')
  assert.strictEqual(seen[0].label, 'save phase progress')
  const cmd = seen[0].prompt
  assert.ok(cmd.includes('phase_progress_entry.py save'), 'rides the phase-progress save')
  assert.ok(cmd.includes('--cost-payload'), 'folds the cost payload into the save')
  assert.ok(cmd.includes('"total":2'), 'carries the proxy dispatch total')
  assert.ok(cmd.includes('"output":500'), 'carries the measured output-token delta')

  // no recordCost -> no cost payload (other persistPhase callers unaffected)
  cm.reset(); seen.length = 0; delete globalThis.__SR_BUDGET
  globalThis.__SR_PHASE = 'plan'; cm.mark('plan'); cm.record('claude-opus-4-8')
  await showrunner.persistPhase('wi', { step: 0, phase: 'plan', record: { phase: 'plan' } })
  assert.ok(!seen[0].prompt.includes('--cost-payload'), 'no cost payload without recordCost')

  // recordCost but an EMPTY phase (no dispatches, unmeasured) -> nothing to record, no cost payload
  cm.reset(); seen.length = 0
  globalThis.__SR_PHASE = 'draft-PR'; cm.mark('draft-PR')
  await showrunner.persistPhase('wi', { step: 6, phase: 'draft-PR', record: { phase: 'draft-PR' }, recordCost: true })
  assert.ok(!seen[0].prompt.includes('--cost-payload'), 'empty phase folds no cost payload')

  delete globalThis.__SR_PHASE
  console.log('ok: showrunner folds phase-cost into the save leaf')
})().catch((e) => { console.error('FAIL:', e.message || e); process.exit(1) })
