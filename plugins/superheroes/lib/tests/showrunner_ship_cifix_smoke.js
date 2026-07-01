const assert = require('assert')
function run(plan) {
  // plan: { checksSeq: [...arrays], ciDecide: 'fix'|'revert_and_gate', fixPush: 'ok'|'dirty' }
  const counts = { ci: 0 }
  global.agent = async (p, opts) => {
    const label = (opts && opts.label) || ''
    if (label === 'exec' && p.includes('build_entry.py')) return [{ index: 0, ok: true, stdout: JSON.stringify({ path: '/wt', outcome: 'reused' }) }]
    if (label === 'exec' && p.includes('rev-parse')) return [{ index: 0, ok: true, stdout: '/wt-head' }]
    if (label === 'lib' && p.includes('reconcile-head')) return { ok: true, head: '/wt-head', reason: 'in sync' }
    if (label === 'lib' && p.includes('--step freshness')) return { decision: 'up_to_date' }
    if (label === 'lib' && p.includes('fence_cli')) return { ok: true }
    if (label === 'exec' && p.includes('--emit-checks')) { const c = plan.checksSeq[Math.min(counts.ci++, plan.checksSeq.length - 1)]; return [{ index: 0, ok: true, stdout: JSON.stringify(c) }] }
    if (label === 'lib' && p.includes('--step ci-decide')) return { action: plan.ciDecide, round: 1, reason: 'r' }
    if (label === 'lib' && p.includes('--step ci-record')) return plan.ciRecord === 'fail' ? { ok: false, reason: 'durable write failed' } : { ok: true }
    if (label === 'fix') return { fixed: true }
    if (label === 'lib' && p.includes('--step fix-push')) {
      if (plan.fixPush === 'dirty') return { ok: false, head: '/wt-head', pushed: false, reason: 'crashed fixer' }
      return { ok: true, head: '/wt-head2', pushed: true, reason: 'fix pushed' }
    }
    if (label === 'lib' && p.includes('--step revert-draft')) return plan.revertDraft === 'fail' ? { ok: false, reason: 'gh timeout' } : { ok: true, reason: 'reverted to draft' }
    if (label === 'lib' && (p.includes('readout') || p.includes('pr_comment'))) return { posted: true }
    throw new Error('unexpected agent: label=' + label + ' prompt=' + p.slice(0, 80))
  }
  global.log = () => {}
  delete require.cache[require.resolve('../showrunner.js')]
  return { sr: require('../showrunner.js'), counts }
}
;(async () => {
  // red -> fix -> push -> green -> ready (FR-3, FR-5: re-judged on the new head)
  let { sr, counts } = run({ checksSeq: [[{ name: 'ci', bucket: 'fail', state: 'failure' }], [{ name: 'ci', bucket: 'pass', state: 'success' }]], ciDecide: 'fix', fixPush: 'ok' })
  let out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'ready', 'red->fix->green -> ready')

  // red -> revert_and_gate -> draft + park (FR-4)
  ;({ sr, counts } = run({ checksSeq: [[{ name: 'ci', bucket: 'fail', state: 'failure' }]], ciDecide: 'revert_and_gate', fixPush: 'ok' }))
  out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'parked', 'revert_and_gate -> parked')
  assert.ok(/pass|draft|check/i.test(out.reason), 'park reason explains the checks could not pass')

  // red -> fix -> fix-push dirty (crashed fixer) -> park, no false ready (UFR-6 partial-failure)
  ;({ sr, counts } = run({ checksSeq: [[{ name: 'ci', bucket: 'fail', state: 'failure' }]], ciDecide: 'fix', fixPush: 'dirty' }))
  out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'parked', 'dirty fix-push -> parked (no false ready)')
  assert.ok(/no false ready|could not push|park/i.test(out.reason), 'dirty fix-push park is honest (UFR-6)')

  // none on the ready head -> honest hand-back, ready-with-carve-out (UFR-3)
  ;({ sr, counts } = run({ checksSeq: [[]], ciDecide: 'fix', fixPush: 'ok' }))
  out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'ready', 'none -> ready (carve-out)')
  assert.ok(/no required checks|did not run|confirm/i.test(out.reason), 'none names the honest carve-out (UFR-3)')

  // FR-5 stale-pass rejection: the leaf marks the rollup stale (PR head != integrated head), so the
  // orchestrator NEVER classifies it as green — it re-waits (bounded) and ends in an honest park.
  ;({ sr, counts } = run({ checksSeq: [{ stale: true, local: 'abc', remote: 'old' }], ciDecide: 'fix', fixPush: 'ok' }))
  out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'parked', 'stale rollup -> never ready (FR-5)')
  assert.ok(/did not complete|confirm CI/i.test(out.reason), 'stale -> honest "checks did not complete" hand-back')
  assert.ok(counts.ci >= 2, 'stale path re-waited (continue), not early-exit')

  // P4: a FAILED draft-flip must NOT let the hand-back claim "returned to draft".
  ;({ sr, counts } = run({ checksSeq: [[{ name: 'ci', bucket: 'fail', state: 'failure' }]], ciDecide: 'revert_and_gate', revertDraft: 'fail' }))
  out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'parked', 'revert_and_gate + failed draft-flip -> parked')
  assert.ok(/could NOT be returned to draft|set it to draft/i.test(out.reason), 'failed draft-flip surfaced honestly (P4)')

  // UFR-5 record-before-push: a failed write-ahead parks BEFORE the fixer/push (the round is never
  // left unrecorded, so the bound can't under-count).
  ;({ sr, counts } = run({ checksSeq: [[{ name: 'ci', bucket: 'fail', state: 'failure' }]], ciDecide: 'fix', ciRecord: 'fail' }))
  out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'parked', 'ci-record durable-write fail -> parked before push (UFR-5)')
  assert.ok(/record the CI-fix round|durable write/i.test(out.reason), 'park names the failed write-ahead')

  console.log('OK: cifix red->fix->ready, revert->park, dirty->park, none->honest-ready, stale->never-green, revert-fail->honest, record-fail->park')
})().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
