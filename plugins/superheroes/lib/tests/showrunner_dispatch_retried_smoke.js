// plugins/superheroes/lib/tests/showrunner_dispatch_retried_smoke.js
// #350 Part B (the silent re-execution disclosure): when dispatchReviewer's cheap-first escalation ladder
// RE-EXECUTES a reviewer dispatch and DISCARDS the already-completed answer (the 2026-07-11 #219 round-4
// signature: a real Important raised then dropped with no trace), the discard decision now journals a LOUD
// `dispatch_retried` event carrying the CAUSE and the discarded result's summary/hash. #394 fixed the
// tier-blind trigger; this is the disclosure safety net for every surviving re-execute-and-discard.
const assert = require('assert')
const panel = require('../review_panel_shell.js')

// Silence the panel's log() so a stray narrator line never fails the run.
global.log = () => {}

;(async () => {
  assert.ok(typeof panel.dispatchReviewer === 'function', 'dispatchReviewer must be exported for the disclosure test')
  assert.ok(panel._retryDiscloseSeam && typeof panel._retryDiscloseSeam.record === 'function',
    'the retry-disclosure seam must be an injectable holder (mirrors showrunner _denialSeam)')

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

  // A dispatch that does NOT re-execute (a clean high-confidence deep answer, no escalation) discloses nothing.
  observed.length = 0
  global.reviewerAgent = async () => ({ findings: [], confidence: 'low' })
  await panel.dispatchReviewer('security-reviewer', context, 'code', '/tmp/rundir', 1, {}, { tier: 'reviewer-deep' })
  assert.strictEqual(observed.length, 0, 'no re-execution -> no disclosure (the event is loud, not noisy)')

  panel._retryDiscloseSeam.record = realRecord
  console.log('ALL OK: showrunner_dispatch_retried_smoke')
})().catch((e) => { console.error(e); process.exit(1) })
