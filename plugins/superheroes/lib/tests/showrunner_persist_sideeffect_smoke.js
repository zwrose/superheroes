// plugins/superheroes/lib/tests/showrunner_persist_sideeffect_smoke.js
// BUG B (live 2026-07-02, review-plan park after 16 agents): persistPhase chains
// `sideEffectCmd && phase_progress_entry.py save` into ONE 'save phase progress' courier. Both
// commands print a JSON line, so the answer is TWO top-level JSON objects on two lines — the
// set-gate result then the save result. The old parse (whole-string JSON.parse + first-{…-last-}
// brace slice) could not read two objects, so runCourierJson threw and persistPhase returned a
// bogus 'phase progress read-back mismatch' — parking a run whose save had actually APPLIED. The
// fix targets the SAVE result (the LAST parseable line). Fenced and unfenced variants; && failure
// semantics preserved (a lone side-effect failure line still surfaces as a park).
const assert = require('assert')
const sr = require('../showrunner.js')

const SET_GATE = JSON.stringify({ ok: true, review: 'changes-requested', status: 'reviewed' })
const SAVE = JSON.stringify({ ok: true, already: false, applied: true, journal_confirmed: true, checkpoint_confirmed: true })

async function persistWith(answer) {
  global.agent = async (prompt, opts) => {
    assert.strictEqual((opts && opts.label), 'save phase progress', 'persist rides ONE save-phase-progress courier')
    assert.ok(prompt.includes('set-gate') && prompt.includes('phase_progress_entry.py save'),
      'the side-effect and the save ride ONE chained courier command')
    return answer
  }
  return sr.persistPhase('wi-x', {
    sideEffectCmd: 'python3 plugins/superheroes/lib/definition_doc.py set-gate --doc plan ' +
      '--work-item wi-x --review changes-requested',
    journalPayload: { phase: 'review-plan', gate: 'changes-requested' },
    step: 3, phase: 'review-plan',
  })
}

;(async () => {
  let res = await persistWith(SET_GATE + '\n' + SAVE)
  assert.strictEqual(res.ok, true, 'a two-JSON-line answer must resolve to the SAVE result and confirm (not park)')

  res = await persistWith('```\n' + SET_GATE + '\n' + SAVE + '\n```')
  assert.strictEqual(res.ok, true, 'a fenced two-JSON-line answer must confirm')

  // Side-effect failure: exit 1 -> `&&` stops -> only the ONE failure line comes back. require()
  // finds the save fields missing and the run parks naming the real reason (never a false confirm).
  res = await persistWith(JSON.stringify({ ok: false, reason: 'stale' }))
  assert.strictEqual(res.ok, false, 'a lone side-effect failure line must surface (the chain stopped)')
  assert.ok(/stale/.test(res.error || ''), 'the real side-effect failure reason surfaces')

  console.log('ok: persistPhase resolves the SAVE result from a two-JSON-line side-effect chain')
})().catch((e) => { console.error('FAIL:', e.message || e); process.exit(1) })
