// plugins/superheroes/lib/tests/showrunner_dispatch_retried_smoke.js
// #350 Part B (the silent re-execution disclosure): when dispatchReviewer's cheap-first escalation ladder
// RE-EXECUTES a reviewer dispatch and DISCARDS the already-completed answer (the 2026-07-11 #219 round-4
// signature: a real Important raised then dropped with no trace), the discard decision now journals a LOUD
// `dispatch_retried` event carrying the CAUSE and the discarded result's summary/hash. #394 fixed the
// tier-blind trigger; this is the disclosure safety net for every surviving re-execute-and-discard.
const assert = require('assert')
const fs = require('fs'); const os = require('os'); const path = require('path')
const panel = require('../review_panel_shell.js')

// Silence the panel's log() so a stray narrator line never fails the run.
global.log = () => {}

;(async () => {
  assert.ok(typeof panel.dispatchReviewer === 'function', 'dispatchReviewer must be exported for the disclosure test')
  assert.ok(panel._retryDiscloseSeam && typeof panel._retryDiscloseSeam.record === 'function',
    'the retry-disclosure seam must be an injectable holder (mirrors showrunner _denialSeam)')

  // (0) REAL PATH: the DEFAULT recorder (_defaultRetryDiscloser) shells its inline python journal.append
  //     through the real io() runHelper (fs-backed spawnSync in node). Drive it WITHOUT swapping the seam
  //     and read the journal back — this pins the JS->Python glue (sys.argv indices, the step/payload/idem
  //     construction) that a swapped observer or a direct journal.append can never catch. spawnSync runs
  //     synchronously, so the line is on disk by the time record() returns.
  {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'sh-350-'))
    const events = path.join(dir, 'events.jsonl')
    const payload = { reviewer: 'code-reviewer', round: 4, cause: 'escalation:reviewer->reviewer-deep', discardedFindings: 2, discardedHash: 'f'.repeat(64) }
    panel._retryDiscloseSeam.record(events, payload)   // the REAL default recorder (not swapped)
    // The recorder is fail-open + fire-and-forget; spawnSync already wrote before record() returned.
    const lines = fs.existsSync(events) ? fs.readFileSync(events, 'utf8').trim().split('\n').filter(Boolean) : []
    assert.strictEqual(lines.length, 1, 'the real recorder wrote exactly one dispatch_retried line: ' + JSON.stringify(lines))
    const ev = JSON.parse(lines[0])
    assert.strictEqual(ev.type, 'dispatch_retried', 'the real journal line is a dispatch_retried event')
    assert.strictEqual(ev.step, 'review:code-reviewer', 'the step tags the reviewer')
    assert.strictEqual(ev.payload.discardedFindings, 2, 'the payload carries the discarded finding count')
    assert.strictEqual(ev.payload.discardedHash, 'f'.repeat(64), 'the payload carries the discarded hash')
    console.log('OK: #350 the REAL _defaultRetryDiscloser writes a valid dispatch_retried event end-to-end (JS->Python glue pinned)')
  }

  // Observe the disclosure without shelling Python (the default recorder is swapped, exactly as the
  // denied-probe smoke swaps _denialSeam).
  const observed = []
  const realRecord = panel._retryDiscloseSeam.record
  panel._retryDiscloseSeam.record = (eventsPath, payload) => observed.push({ eventsPath, payload })

  // Cheap 'reviewer' tier returns a FINDINGS-bearing answer (shaped confidence:'low' by design) — the
  // escalation branch fires, re-dispatches deep, and DISCARDS this completed answer with its one finding.
  let call = 0
  global.reviewerAgent = async (_reviewer, _context, _rubric, _runDir, _round, opts) => {
    call += 1
    if ((opts && opts.tier) === 'reviewer') {
      // legacy array at cheap tier -> _shapeReviewerResult stamps confidence:'low' with the findings.
      return [{ file: 'pr_body.py', line: 12, title: 'Malformed pr-body context still drives the composer', severity: 'Important', evidence: 'x' }]
    }
    return { findings: [], confidence: 'low' }   // deep answer: valid, not retryable -> adopted, loop ends
  }

  const roundFindings = {}
  const context = { workItem: 'wi-219', eventsPath: '/tmp/wi-219-events.jsonl' }
  await panel.dispatchReviewer('code-reviewer', context, 'code', '/tmp/rundir', 4, roundFindings, { tier: 'reviewer' })

  assert.strictEqual(observed.length, 1, 'exactly one re-execute-and-discard disclosure fires for the escalation')
  const { eventsPath, payload } = observed[0]
  assert.strictEqual(eventsPath, '/tmp/wi-219-events.jsonl', 'the disclosure is journaled to the run journal (context.eventsPath)')
  assert.ok(/escalation:reviewer->reviewer-deep/.test(payload.cause), 'the cause names the re-dispatch trigger: ' + payload.cause)
  assert.strictEqual(payload.reviewer, 'code-reviewer', 'the disclosure names the reviewer whose answer was discarded')
  assert.strictEqual(payload.round, 4, 'the disclosure names the round')
  assert.strictEqual(payload.discardedFindings, 1, 'the disclosure carries the discarded answer finding COUNT (a dropped Important is visible)')
  assert.ok(/^[0-9a-f]{64}$/.test(payload.discardedHash), 'the disclosure carries a sha256 of the discarded answer: ' + payload.discardedHash)

  // The adopted (deep) answer still becomes the round record — the disclosure never changes the outcome.
  assert.ok(roundFindings['code-reviewer'] && roundFindings['code-reviewer'].escalated === true,
    'the escalation is still recorded on the round finding')

  // NEGATIVE (same tier, isolates re-execution as the ONLY variable vs the positive case): at tier
  // 'reviewer' an EMPTY-findings answer is stamped confidence:'high' by _shapeReviewerResult, so the
  // escalation guard is false — no re-dispatch, so no disclosure. Proves the event is gated on actual
  // re-execution, not merely on running at the cheap tier.
  observed.length = 0
  const rf2 = {}
  global.reviewerAgent = async () => []   // legacy empty array -> confidence:'high' at cheap tier
  await panel.dispatchReviewer('security-reviewer', context, 'code', '/tmp/rundir', 1, rf2, { tier: 'reviewer' })
  assert.strictEqual(observed.length, 0, 'no re-execution -> no disclosure (the event is loud, not noisy)')
  assert.ok(rf2['security-reviewer'] && rf2['security-reviewer'].escalated === false, 'the clean cheap answer did NOT escalate')

  // And a clean deep answer (different guard) also discloses nothing.
  observed.length = 0
  global.reviewerAgent = async () => ({ findings: [], confidence: 'low' })
  await panel.dispatchReviewer('security-reviewer', context, 'code', '/tmp/rundir', 1, {}, { tier: 'reviewer-deep' })
  assert.strictEqual(observed.length, 0, 'a non-retryable deep answer does not re-execute -> no disclosure')

  panel._retryDiscloseSeam.record = realRecord
  console.log('ALL OK: showrunner_dispatch_retried_smoke')
})().catch((e) => { console.error(e); process.exit(1) })
