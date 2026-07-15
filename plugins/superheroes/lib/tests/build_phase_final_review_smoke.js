require('./_smoke_checkout_root.js')
// plugins/superheroes/lib/tests/build_phase_final_review_smoke.js
// #115: runFinalReview drives the in-memory panel (single-reviewer code leg). The reviewer RETURNS a
// findings[] array (no findings-generalist.json); merge/tally run in-process via the parity-locked
// twins; the verify gate still runs verify_gate.py via a leaf. Pins terminal 'clean' (no findings +
// verify pass) and terminal 'halted' (verify fail blocks a clean certification, FR-17/UFR-4).
// #115 increment A: verify_command_cli.py + minor_rollup_cli.py are ported to exec(raw)+parse (they
// route through the 'exec' label, stdout a JSON string). model_tier is now an in-process twin (no
// leaf) — its routes are gone (reviewerModel/fixerModel come from model_tier.js directly).
// #381: the leg is ONE review pass + ONE fix pass (maxRounds:1, fix dispatched post-cap-halt, one
// post-fix verify, no re-review). Scenarios 4-8 pin the revised contract: round-cap handoff (fix
// dispatched exactly once, post-fix verify runs, haltKind survives as 'round-cap'), pre-fix verify
// red parks WITHOUT a fix dispatch, post-fix verify red parks, fix-dispatch failure parks, fence
// lost parks — all discriminated on the STRUCTURED haltKind, never prose.
const assert = require('assert')
const fs = require('fs'); const os = require('os'); const path = require('path')
global.log = () => {}
global.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))

// Per-scenario counters (reset before each makeAgent install).
let fixDispatches = 0
let verifyCalls = 0
let reviewerCalls = 0
let lastFixBranchPrompt = ''   // #375: the native whole-branch fixer prompt (must carry the sentinel trailer)

// reviewerFindings: what the (single) reviewer leaf returns this run. reviewerConfidence (optional):
// when set, rides through branch-reviewer so the panel gate sees cannot-certify. verifyResult: the
// classification ('pass'|'fail'|'timeout'|'skipped') for the ROUND's verify; postFixVerifyResult (if
// set) is what the SECOND verify call — the #381 post-fix verify — classifies as. fence:false answers
// the fence-lease leaf {ok:false} (a lost lease). fixBranch: optional override for the native fixer
// leaf (a function may throw to simulate a failed fix dispatch). The config IO leaves route through
// the 'exec'-shaped labels and return the exec array shape. #115 Task 16: verifyAgent emits raw run
// data ({command,returncode,timedOut}) for the JS twin to classify.
function makeAgent({ reviewerFindings, reviewerConfidence, verifyResult, postFixVerifyResult, fence = true, fixBranch }) {
  fixDispatches = 0
  verifyCalls = 0
  reviewerCalls = 0
  // Map a desired classify result back to the raw run data that produces it
  function runDataFor(result) {
    if (result === 'skipped') return { command: 'none', returncode: null, timedOut: false }
    if (result === 'timeout') return { command: 'pytest -q', returncode: null, timedOut: true }
    if (result === 'pass')    return { command: 'pytest -q', returncode: 0,    timedOut: false }
    return                           { command: 'pytest -q', returncode: 1,    timedOut: false }  // fail
  }
  function writeVerifyOut(prompt, result) {
    const m = String(prompt || '').match(/--out '([^']+)'/)
    if (!m) return
    const payload = result === 'pass' ? { result: 'pass', code: 0, tail: '' }
      : result === 'skipped' ? { result: 'skipped', code: null, tail: '' }
      : result === 'timeout' ? { result: 'timeout', code: null, tail: '' }
      : { result: 'fail', code: 1, tail: 'Failed to resolve import "next/server" in route.test.ts' }
    fs.writeFileSync(m[1], JSON.stringify(payload))
  }
  return async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    if (label === 'resume') return '1'
    if (label.startsWith('branch-reviewer:')) {
      reviewerCalls += 1
      const payload = { findings: reviewerFindings }
      if (reviewerConfidence) payload.confidence = reviewerConfidence
      return payload
    }
    if (label === 'fence lease') {
      return [{ ok: true, stdout: JSON.stringify({ ok: !!fence }) }]
    }
    if (label === 'fix-branch') {
      fixDispatches += 1
      lastFixBranchPrompt = prompt   // #375: capture the NATIVE (default Claude) whole-branch fix prompt
      if (typeof fixBranch === 'function') return fixBranch()
      return { ok: true }
    }
    if (label === 'run verify') {
      verifyCalls += 1
      const result = (verifyCalls > 1 && postFixVerifyResult) ? postFixVerifyResult : verifyResult
      if (result === 'garbled-no-command') return { returncode: 1, timedOut: false }
      writeVerifyOut(prompt, result)
      return runDataFor(result)
    }
    if (label === 'read verify + minors') {
      return [{ ok: true, stdout: JSON.stringify({ ok: true, verify_command: 'pytest -q', minors: [] }) }]
    }
    return ''
  }
}

global.recordDeferred = async () => {}
// pid-unique runDir + reason-bearing terminal assertions (see _final_review_probe.js;
// must load before build_phase.js binds reviewPanel).
const { uniqueWorkItem, resetRunDir, runDirFor, assertTerminal } = require('./_final_review_probe.js')
const bp = require('../build_phase.js')

;(async () => {
  const WI = uniqueWorkItem()
  // One reset up front: hermetic start (no stale accumulator), while the three calls below
  // still share the runDir exactly as before (the resume decider sees the accumulated rounds).
  resetRunDir(WI)

  // 1. Clean single-round final review: no findings + verify pass -> terminal 'clean'. #381 (e): a
  //    clean round dispatches ZERO fixers.
  global.agent = makeAgent({ reviewerFindings: [], verifyResult: 'pass' })
  let r = await bp.runFinalReview(WI, 5, 'superheroes/wi-abc',
    fs.mkdtempSync(path.join(os.tmpdir(), 'fr-')))
  assertTerminal(r, 'clean', 'no findings + verify pass certifies clean')
  assert.strictEqual(fixDispatches, 0, '#381 (e): a clean round dispatches no fixer')

  // 2. Verify fails -> a clean-looking round cannot certify clean -> terminal 'halted'
  //    (the caller parks, UFR-4). No findings, so the only thing blocking clean is the verify gate.
  global.agent = makeAgent({ reviewerFindings: [], verifyResult: 'fail' })
  r = await bp.runFinalReview(WI, 5, 'superheroes/wi-abc',
    fs.mkdtempSync(path.join(os.tmpdir(), 'fr-')))
  assertTerminal(r, 'halted', 'a failing verify blocks a clean certification (FR-17/UFR-4)')
  // #279: the halted verdict carries an honest reason naming the failing stage + the verify error
  // head, so the caller's park says WHY (verify, with the resolve error) rather than a bare 'halted'.
  assert.ok(/verify failed r\d+/.test(r.reason || ''), '#279: final-review reason names the verify stage')
  assert.ok(/Failed to resolve import/.test(r.reason || ''), '#279: final-review reason carries the verify error head')

  // 3. FIX 2 (#115 final review): a GARBLED verify leaf that DROPS its `command` echo but reports a
  //    real failure (returncode 1) under a REAL verifyCommand must NOT be misclassified 'skipped'
  //    (which would certify clean). The spine classifies with the command it knows -> 'fail' ->
  //    the clean-looking round CANNOT certify -> terminal 'halted'.
  global.agent = makeAgent({ reviewerFindings: [], verifyResult: 'garbled-no-command' })
  r = await bp.runFinalReview(WI, 5, 'superheroes/wi-abc',
    fs.mkdtempSync(path.join(os.tmpdir(), 'fr-')))
  assertTerminal(r, 'halted',
    'a verify failure with a dropped command echo must classify fail (not skipped) -> no clean certify')

  // 4. #381 ROUND-CAP HANDOFF (a): the single review pass (maxRounds:1) surfaces a blocker at the
  //    one-pass cap with verify PASS -> the ONE fix pass dispatches EXACTLY ONCE (fence-before-write,
  //    native fixer leaf), the post-fix verify runs ONCE more (the fix changed the tree), and the
  //    result is terminal 'halted' + haltKind 'round-cap' — the shape the caller hands off to
  //    review-code. The open finding is summarized (no evidence walls) for the handoff journal, and
  //    the fixed ids reach the deferred-set (the audit channel the shell's runFixStep would write).
  const blocker = [{ file: 'a.js', line: 1, title: 'branch bug', severity: 'Critical', evidence: 'e' }]
  resetRunDir(WI)
  global.agent = makeAgent({ reviewerFindings: blocker, verifyResult: 'pass' })
  r = await bp.runFinalReview(WI, 5, 'superheroes/wi-abc',
    fs.mkdtempSync(path.join(os.tmpdir(), 'fr-')))
  assertTerminal(r, 'halted', '#381: a blocker at the one-pass cap halts (round-cap), not clean')
  assert.strictEqual(r.haltKind, 'round-cap', '#381: the halt carries the round-cap discriminator')
  assert.strictEqual(reviewerCalls, 1, '#381 (a): exactly one review pass — no post-fix re-review')
  assert.strictEqual(fixDispatches, 1, '#381 (a): the fix batch dispatches EXACTLY ONCE (no loop)')
  // #375: the NATIVE (default-Claude) whole-branch fixer is the COMMON path (engine fails open to
  // 'claude'); its inline prompt — NOT fixBranchPrompt (that is the external-dispatch prompt) — must
  // instruct the reserved sentinel trailer, or the default-engine final-review fix commit carries no
  // Task-Id and the resume fail-closes on UFR-7 (the exact #375 bug on the most common config).
  assert.ok(lastFixBranchPrompt.includes('Task-Id: final-review'),
    '#375: the native whole-branch fixer prompt instructs the reserved final-review sentinel trailer')
  assert.strictEqual(verifyCalls, 2, '#381 (a): the post-fix verify runs once (round verify + post-fix)')
  assert.deepStrictEqual(r.fixPass, { dispatched: true, fixed: ['branch bug'], postVerify: 'pass' },
    '#381 (a): the fix-pass facts ride the result for the handoff journal')
  assert.strictEqual(r.openFindingsCount, 1, '#381: the open finding is summarized for the handoff journal')
  assert.strictEqual((r.openFindings[0] || {}).title, 'branch bug', '#381: the summary carries the finding identity')
  const deferredSet = JSON.parse(fs.readFileSync(`${runDirFor(WI)}/deferred-set.json`, 'utf8'))
  assert.ok(Object.prototype.hasOwnProperty.call(deferredSet, 'branch bug'),
    '#381 (a): the fix report ids reach the deferred-set (audit channel, as the shell would record)')

  // 4b. #381 UNCERTIFIED CAP PARK (h): low-confidence reviewer output with a blocker at cap 1 must
  //     PARK — no fix dispatch, no handoff/stamp side effects. haltKind is 'other', not 'round-cap'.
  resetRunDir(WI)
  global.agent = makeAgent({ reviewerFindings: blocker, reviewerConfidence: 'low', verifyResult: 'pass' })
  r = await bp.runFinalReview(WI, 5, 'superheroes/wi-abc',
    fs.mkdtempSync(path.join(os.tmpdir(), 'fr-')))
  assertTerminal(r, 'halted', '#381 (h): an uncertified cap halt parks')
  assert.strictEqual(r.haltKind, 'other', '#381 (h): uncertified cap is other — never round-cap handoff')
  assert.strictEqual(r.uncertified, true, '#381 (h): the uncertified flag rides the result')
  assert.strictEqual(reviewerCalls, 1, '#381 (h): exactly one review pass')
  assert.strictEqual(fixDispatches, 0, '#381 (h): uncertified cap dispatches no fixer')
  assert.strictEqual(verifyCalls, 1, '#381 (h): only the round verify runs — no post-fix verify')

  // 5. #381 PRE-FIX VERIFY-FAIL SWALLOW-TRAP GUARD: a blocker at the cap whose ROUND verify goes red
  //    must NOT read as 'round-cap' — it is 'verify-fail', PARKS, and dispatches NO fixer (the park
  //    is decided before any fix attempt; fail-closed preserved).
  resetRunDir(WI)
  global.agent = makeAgent({ reviewerFindings: blocker, verifyResult: 'fail' })
  r = await bp.runFinalReview(WI, 5, 'superheroes/wi-abc',
    fs.mkdtempSync(path.join(os.tmpdir(), 'fr-')))
  assertTerminal(r, 'halted', '#381: a blocker + red round verify halts')
  assert.strictEqual(r.haltKind, 'verify-fail',
    '#381: a red verify must dominate the cap halt (never swallowed into a round-cap proceed)')
  assert.strictEqual(fixDispatches, 0, '#381: a pre-fix red verify parks with no fix dispatch')

  // 6. #381 POST-FIX VERIFY RED (b): round verify passes, the fix batch lands, but the post-fix
  //    verify goes red — the handoff is withdrawn: haltKind 'verify-fail' -> the caller PARKS. The
  //    fix pass still ran exactly once (that is the observable proof the tree changed before verify).
  resetRunDir(WI)
  global.agent = makeAgent({ reviewerFindings: blocker, verifyResult: 'pass', postFixVerifyResult: 'fail' })
  r = await bp.runFinalReview(WI, 5, 'superheroes/wi-abc',
    fs.mkdtempSync(path.join(os.tmpdir(), 'fr-')))
  assertTerminal(r, 'halted', '#381 (b): a post-fix red verify halts')
  assert.strictEqual(r.haltKind, 'verify-fail', '#381 (b): the post-fix red verify parks — never hands off')
  assert.ok(/post-fix verify failed/.test(r.reason || ''), '#381 (b): the reason names the post-fix verify stage')
  assert.strictEqual(fixDispatches, 1, '#381 (b): the one fix pass ran before the post-fix verify')

  // 6b. #381 POST-FIX VERIFY TIMEOUT (b-timeout): round verify passes, the fix batch lands, but the
  //     post-fix verify times out — the handoff is withdrawn: haltKind 'verify-fail' -> the caller
  //     PARKS (no journal, no stamp-and-advance on the buildPhase path).
  resetRunDir(WI)
  global.agent = makeAgent({ reviewerFindings: blocker, verifyResult: 'pass', postFixVerifyResult: 'timeout' })
  r = await bp.runFinalReview(WI, 5, 'superheroes/wi-abc',
    fs.mkdtempSync(path.join(os.tmpdir(), 'fr-')))
  assertTerminal(r, 'halted', '#381 (b-timeout): a post-fix verify timeout halts')
  assert.strictEqual(r.haltKind, 'verify-fail', '#381 (b-timeout): the post-fix timeout parks — never hands off')
  assert.ok(/post-fix verify timed out/.test(r.reason || ''), '#381 (b-timeout): the reason names the post-fix verify timeout')
  assert.strictEqual(fixDispatches, 1, '#381 (b-timeout): the one fix pass ran before the post-fix verify')
  assert.strictEqual(verifyCalls, 2, '#381 (b-timeout): the post-fix verify runs once (round verify + post-fix)')

  // 7. #381 FIX DISPATCH FAILURE (c): the fixer leaf throws -> the fix batch did not land ->
  //    haltKind 'fix-failed' -> the caller PARKS (fail-closed). No post-fix verify runs.
  resetRunDir(WI)
  global.agent = makeAgent({ reviewerFindings: blocker, verifyResult: 'pass',
    fixBranch: () => { throw new Error('fixer leaf crashed') } })
  r = await bp.runFinalReview(WI, 5, 'superheroes/wi-abc',
    fs.mkdtempSync(path.join(os.tmpdir(), 'fr-')))
  assertTerminal(r, 'halted', '#381 (c): a failed fix dispatch halts')
  assert.strictEqual(r.haltKind, 'fix-failed', '#381 (c): a failed fix dispatch parks (fail-closed)')
  assert.strictEqual(fixDispatches, 1, '#381 (c): the one fix pass was attempted before it failed')
  assert.strictEqual(verifyCalls, 1, '#381 (c): no post-fix verify after a failed fix dispatch')

  // 8. #381 FENCE LOST (d): the lease fence answers not-ok before the fix write -> fixStep returns
  //    null -> haltKind 'fix-failed' -> PARK. No fixer dispatch happens over a lost fence (UFR-10).
  resetRunDir(WI)
  global.agent = makeAgent({ reviewerFindings: blocker, verifyResult: 'pass', fence: false })
  r = await bp.runFinalReview(WI, 5, 'superheroes/wi-abc',
    fs.mkdtempSync(path.join(os.tmpdir(), 'fr-')))
  assertTerminal(r, 'halted', '#381 (d): a lost fence halts')
  assert.strictEqual(r.haltKind, 'fix-failed', '#381 (d): a lost fence parks (fail-closed, UFR-10)')
  assert.strictEqual(fixDispatches, 0, '#381 (d): NO fixer dispatch over a lost fence (UFR-10)')

  // 9. #381 CITATION-LESS BLOCKER (f): a blocking finding with line:null is counted by the cap
  //    decider (presentBlocking) but dropped from verdict.findings by compileFindings. The cap
  //    worklist must still dispatch the fix batch and journal open_findings_count 1, not 0.
  const citationlessBlocker = [{ file: 'b.js', line: null, title: 'missing line', severity: 'Critical', evidence: 'e' }]
  resetRunDir(WI)
  global.agent = makeAgent({ reviewerFindings: citationlessBlocker, verifyResult: 'pass' })
  r = await bp.runFinalReview(WI, 5, 'superheroes/wi-abc',
    fs.mkdtempSync(path.join(os.tmpdir(), 'fr-')))
  assertTerminal(r, 'halted', '#381 (f): a citation-less blocker at the cap halts (round-cap)')
  assert.strictEqual(r.haltKind, 'round-cap', '#381 (f): the halt carries the round-cap discriminator')
  assert.strictEqual(fixDispatches, 1, '#381 (f): citation-less blocker still dispatches the fix batch')
  assert.strictEqual(r.openFindingsCount, 1, '#381 (f): handoff summary counts the citation-less blocker')
  assert.strictEqual((r.openFindings[0] || {}).title, 'missing line')

  // 10. #381 INCONSISTENT EMPTY WORKLIST (g): round-cap with an empty derived cap worklist is an
  //     inconsistency with the decider — downgrade to 'other' (park), never stamp-and-advance.
  resetRunDir(WI)
  const ioSeam = require('../io_seam.js')
  const baseIo = ioSeam.io()
  globalThis.io = Object.assign({}, baseIo, {
    readText: async (p) => {
      if (String(p).endsWith('round-records.json')) return '[]'
      return baseIo.readText(p)
    },
  })
  delete require.cache[require.resolve('../build_phase.js')]
  const bpPark = require('../build_phase.js')
  global.agent = makeAgent({ reviewerFindings: blocker, verifyResult: 'pass' })
  r = await bpPark.runFinalReview(WI, 5, 'superheroes/wi-abc',
    fs.mkdtempSync(path.join(os.tmpdir(), 'fr-')))
  assertTerminal(r, 'halted', '#381 (g): inconsistent empty cap worklist halts')
  assert.strictEqual(r.haltKind, 'other', '#381 (g): empty worklist downgrades round-cap to other (park)')
  assert.ok(/empty blocking worklist/i.test(r.reason || ''), '#381 (g): reason names the inconsistency')
  assert.strictEqual(fixDispatches, 0, '#381 (g): NO fix dispatch when the cap worklist is empty')
  delete globalThis.io
  delete require.cache[require.resolve('../build_phase.js')]

  console.log('ok: build_phase final review clean + halted + garbled-verify-fail-closed + #381 one-fix-pass contract (round-cap handoff, pre/post-fix verify red+timeout, fix-failure, fence-lost, citation-less blocker, empty-worklist park)')
})().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
