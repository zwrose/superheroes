// #434: a relaunched review leg re-enters a PARKED phase and parks again with a byte-identical payload;
// phase_progress_entry.py keyed freshness on payload-equality and deduped the second park's
// phase_record/phase_cost/parked away (journal quieter than the allowance ledger). persistPhase now mints
// a resume-continuing per-leg idem nonce on a park and bakes it into the save command so a genuine
// re-entry earns its own records while a courier retry of one save dedupes. This smoke pins the JS glue:
// a park issues the seed read then the save carrying `--leg-idem pp:<wi>:s<step>:<phase>:d<max+1>`; a
// completed (proceed) phase mints NOTHING; an unseedable journal omits the flag (legacy path).
const assert = require('assert')
const showrunner = require('../showrunner.js')
const { markedStdout, saveProgressOk } = require('./_marked_stdout.js')

function runWith({ seedMax, seedFails }) {
  const prompts = []
  global.log = () => {}
  global.agent = async (prompt, opts) => {
    prompts.push({ label: opts.label, prompt })
    if (opts.label === 'phase leg seed') {
      return seedFails ? markedStdout({ ok: false, error: 'unseedable' })
        : markedStdout({ ok: true, max: seedMax })
    }
    return saveProgressOk({ checkpoint_confirmed: false })
  }
  return prompts
}

function savePrompt(prompts) {
  const hit = prompts.find((p) => p.label === 'save phase progress')
  return hit ? hit.prompt : ''
}

;(async () => {
  // 1) leg 1 on a fresh journal (seed max=0) -> save carries pp:wi:s5:review-plan:d1.
  let prompts = runWith({ seedMax: 0 })
  let res = await showrunner.persistPhase('wi', {
    step: 5, phase: 'review-plan', journalOnly: true, recordCost: true,
    parkReason: 'no net progress',
    record: { phase: 'review-plan', gate: 'changes-requested', confidence: 'high' },
  })
  assert.strictEqual(res.ok, true, 'leg-1 park save confirmed')
  assert.deepStrictEqual(prompts.map((p) => p.label), ['phase leg seed', 'save phase progress'],
    'a park reads the seed then saves')
  assert.ok(/--leg-idem 'pp:wi:s5:review-plan:d1'/.test(savePrompt(prompts)),
    'leg-1 save bakes the d1 nonce')

  // 2) leg 2 (relaunch): the journal already holds d1, so the seed reads max=1 -> save carries d2. A
  // DISTINCT nonce is what lets phase_progress_entry.py record the second park instead of deduping it.
  prompts = runWith({ seedMax: 1 })
  res = await showrunner.persistPhase('wi', {
    step: 5, phase: 'review-plan', journalOnly: true, recordCost: true,
    parkReason: 'no net progress',
    record: { phase: 'review-plan', gate: 'changes-requested', confidence: 'high' },
  })
  assert.ok(/--leg-idem 'pp:wi:s5:review-plan:d2'/.test(savePrompt(prompts)),
    'relaunch leg-2 bakes the resume-continued d2 nonce')

  // 3) a completed (proceed) phase is NOT journal-only: it advances the cursor, a resume skips it, so it
  // can never double-record — no seed read, no --leg-idem (byte-unchanged compose).
  prompts = runWith({ seedMax: 9 })
  res = await showrunner.persistPhase('wi', {
    step: 5, phase: 'review-plan',
    record: { phase: 'review-plan', gate: 'passed' },
  })
  assert.deepStrictEqual(prompts.map((p) => p.label), ['save phase progress'],
    'a completed phase mints no leg nonce')
  assert.ok(!/--leg-idem/.test(savePrompt(prompts)), 'completed-phase save carries no --leg-idem')

  // 4) an unseedable journal (seed read fails) carries --leg-force, NOT --leg-idem: the park still
  // ALWAYS records (fail-safe TOWARD recording, the #350 direction) instead of silently reverting to
  // payload-equality dedup and re-hiding the relaunch park on a transient seed drop (premortem finding).
  prompts = runWith({ seedFails: true })
  res = await showrunner.persistPhase('wi', {
    step: 5, phase: 'review-plan', journalOnly: true, recordCost: true, parkReason: 'x',
    record: { phase: 'review-plan', gate: 'changes-requested' },
  })
  assert.ok(!/--leg-idem/.test(savePrompt(prompts)), 'unseedable park carries no --leg-idem')
  assert.ok(/--leg-force/.test(savePrompt(prompts)), 'unseedable park force-records (fail-safe toward recording)')

  console.log('ok: showrunner phase relaunch leg nonce')
})().catch((e) => { console.error('FAIL:', e.message || e); process.exit(1) })
