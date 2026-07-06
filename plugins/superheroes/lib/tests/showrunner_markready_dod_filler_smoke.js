// mark-ready DoD fill leg (issue #228 "build/ship legs fill it"; PR #251 review batch:
// the model PROPOSES rows, the deterministic splice CLI holds the pen). Scenarios:
// dod-park -> propose -> splice -> re-decide -> ready; splice/proposal failure -> the
// original honest park stands (no loop); non-dod park never dispatches anything; a
// transport failure on the re-decide keeps the specific DoD park reason.
require('./_smoke_checkout_root.js')
const assert = require('assert')

const DOD_PARK = { ok: false, read_back: false, gate: 'dod', pr: 77, reason: 'DoD gate: bullet X — no disposition (expected done or deferred)' }

function run(plan) {
  const labels = []
  let gateCalls = 0
  global.log = () => {}
  global.agent = async (_prompt, opts) => {
    const label = (opts && opts.label) || ''
    labels.push(label)
    if (label === 'mark PR ready') {
      gateCalls += 1
      const out = plan.gateSeq[Math.min(gateCalls - 1, plan.gateSeq.length - 1)]
      if (out === 'transport') throw new Error('courier transport failure')
      return [{ ok: true, stdout: JSON.stringify(out) }]
    }
    if (label === 'resolve review target') {
      return [{ ok: true, stdout: JSON.stringify({ ok: true, worktree: '/wt-dod', expectedHead: 'h0' }) }]
    }
    if (label === 'wait for CI to settle') {
      assert.ok(String(_prompt).includes('ci_settle_cli.py'), 'pre-propose settle runs the settle CLI')
      assert.ok(String(_prompt).includes('--timeout-sec 540'), 'settle budget pinned under the Bash floor')
      assert.ok(String(_prompt).includes("--worktree '/wt-dod'"), 'settle reads checks from the BUILD worktree — from the checkout root the stale guard short-circuits without waiting (PR #261 review)')
      return [{ ok: true, stdout: JSON.stringify({ settled: true, waited_sec: 0.0, checks: [] }) }]
    }
    if (label === 'fill-dod') {
      assert.ok(String(_prompt).includes('#77'), 'proposal prompt carries the PR number')
      assert.ok(String(_prompt).includes('OMIT it'), 'proposal prompt carries the honesty contract')
      assert.ok(!String(_prompt).includes('--root .'), 'proposal prompt commands are rooted (abs root, not cwd-relative)')
      // finding #17: the leaf (already opus via the bundle's smart-leaf floor) must be told to
      // evidence EVERY bullet, with structural bullets pointed at the diff — an opus leaf still
      // omitted 2 of 3 evidenceable bullets on run 11.
      assert.ok(String(_prompt).includes('EVERY Definition-of-done bullet'), 'proposal prompt demands completeness (one row per bullet)')
      assert.ok(String(_prompt).includes('--name-only'), 'proposal prompt points structural bullets at gh pr diff --name-only')
      if (plan.propose === 'crash') throw new Error('leaf crashed')
      return plan.propose
    }
    if (label === 'splice DoD dispositions') {
      assert.ok(String(_prompt).includes('dod_fill_cli.py'), 'splice runs the deterministic CLI')
      return [{ ok: true, stdout: JSON.stringify(plan.splice) }]
    }
    throw new Error(`unexpected label ${label || 'none'}`)
  }
  delete require.cache[require.resolve('../showrunner.js')]
  return { sr: require('../showrunner.js'), labels }
}

;(async () => {
  // happy path: park -> propose -> splice -> re-decide flips ready.
  let { sr, labels } = run({
    gateSeq: [DOD_PARK, { ok: true, read_back: true }],
    propose: { ok: true, rows: [{ bullet: 'bullet X', disposition: 'done', detail: 'evidence' }] },
    splice: { ok: true, filled: 1, rejected: [] },
  })
  let out = await sr.markReadyPhase('wi-dod')
  assert.strictEqual(out.phaseResult.confidence, 'high')
  assert.deepStrictEqual(out.sideEffect, { ready: true })
  assert.deepStrictEqual(labels, ['mark PR ready', 'resolve review target', 'wait for CI to settle', 'fill-dod', 'splice DoD dispositions', 'mark PR ready'])
  // finding #12: the settle leg precedes the proposal so the "green CI" bullet is
  // evidenceable — pending checks parked a fresh fast run at this gate (run fdfad511).

  // splice rejects everything -> no re-decide, the original DoD park reason survives.
  ;({ sr, labels } = run({
    gateSeq: [DOD_PARK],
    propose: { ok: true, rows: [{ bullet: 'bullet X', disposition: 'done', detail: 'fabricated' }] },
    splice: { ok: false, filled: 0, rejected: [{ bullet: 'bullet X', reason: 'path-shaped evidence does not exist' }] },
  }))
  out = await sr.markReadyPhase('wi-dod')
  assert.strictEqual(out.phaseResult.confidence, 'low')
  assert.ok(out.phaseResult.assumptions[0].includes('DoD gate'), 'park keeps the gate reason')
  assert.deepStrictEqual(labels, ['mark PR ready', 'resolve review target', 'wait for CI to settle', 'fill-dod', 'splice DoD dispositions'])

  // proposal returns no rows -> no splice, no re-decide.
  ;({ sr, labels } = run({ gateSeq: [DOD_PARK], propose: { ok: true, rows: [] }, splice: { ok: true } }))
  out = await sr.markReadyPhase('wi-dod')
  assert.strictEqual(out.phaseResult.confidence, 'low')
  assert.deepStrictEqual(labels, ['mark PR ready', 'resolve review target', 'wait for CI to settle', 'fill-dod'])

  // proposal leaf crash -> original park stands.
  ;({ sr, labels } = run({ gateSeq: [DOD_PARK], propose: 'crash', splice: { ok: true } }))
  out = await sr.markReadyPhase('wi-dod')
  assert.strictEqual(out.phaseResult.confidence, 'low')
  assert.deepStrictEqual(labels, ['mark PR ready', 'resolve review target', 'wait for CI to settle', 'fill-dod'])

  // non-dod park never dispatches the fill leg.
  ;({ sr, labels } = run({ gateSeq: [{ ok: false, read_back: false, reason: 'PR isDraft unreadable — not flipping blind' }], propose: { ok: true, rows: [] }, splice: { ok: true } }))
  out = await sr.markReadyPhase('wi-plain')
  assert.deepStrictEqual(labels, ['mark PR ready'])

  // stringified leaf payload (ok:'true', rows:'[...]') still splices — boundary coercion
  // (#115 class; observed live in proof run wf_a9654118: the leaf stringified both fields).
  ;({ sr, labels } = run({
    gateSeq: [DOD_PARK, { ok: true, read_back: true }],
    propose: { ok: 'true', rows: JSON.stringify([{ bullet: 'bullet X', disposition: 'done', detail: 'evidence' }]) },
    splice: { ok: true, filled: 1, rejected: [] },
  }))
  out = await sr.markReadyPhase('wi-dod')
  assert.strictEqual(out.phaseResult.confidence, 'high', 'stringified rows are coerced, not dropped')
  assert.deepStrictEqual(labels, ['mark PR ready', 'resolve review target', 'wait for CI to settle', 'fill-dod', 'splice DoD dispositions', 'mark PR ready'])

  // stringified ok:'false' is FALSE (a truthy-string trap) -> no splice, park stands.
  ;({ sr, labels } = run({
    gateSeq: [DOD_PARK],
    propose: { ok: 'false', rows: JSON.stringify([{ bullet: 'bullet X', disposition: 'done', detail: 'evidence' }]) },
    splice: { ok: true },
  }))
  out = await sr.markReadyPhase('wi-dod')
  assert.strictEqual(out.phaseResult.confidence, 'low')
  assert.deepStrictEqual(labels, ['mark PR ready', 'resolve review target', 'wait for CI to settle', 'fill-dod'], "ok:'false' never splices")

  // transport failure on the re-decide keeps the specific DoD park reason (not the generic).
  ;({ sr, labels } = run({
    gateSeq: [DOD_PARK, 'transport'],
    propose: { ok: true, rows: [{ bullet: 'bullet X', disposition: 'done', detail: 'evidence' }] },
    splice: { ok: true, filled: 1, rejected: [] },
  }))
  out = await sr.markReadyPhase('wi-dod')
  assert.strictEqual(out.phaseResult.confidence, 'low')
  assert.ok(out.phaseResult.assumptions[0].includes('DoD gate'), 're-decide transport failure preserves the DoD reason')

  console.log('ok: dod propose->splice->re-decide (happy, reject, empty, crash, non-dod, stringified, ok-false-string, retry-transport)')
})().catch((e) => { console.error('FAIL:', e.message || e); process.exit(1) })
