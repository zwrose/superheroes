// plugins/superheroes/lib/tests/showrunner_engine_review_smoke.js
// TDD smoke for Task 12 (#38): reviewCodeLeaves engine branch + startup __SR_ENGINE_PREFS load.
//
// PART A: showrunner() startup issues an exec containing engine_pref_load.py and plants the parsed
//   {reviewer, implementation, effort} map on globalThis.__SR_ENGINE_PREFS (mirrors Task 17's
//   __SR_OVERRIDES pipe). Fail-safe: a bad/unreadable parse yields both-'claude' + empty effort.
//
// PART B: reviewCodePhase's reviewerAgent (read-only) and fixStep (write) route through
//   engineDispatch.dispatchExternal when the resolved engine != 'claude' — reviewer engine for
//   review, implementation engine for fix (FR-15). UFR-7: an unreadable/incomplete external review
//   falls open to the native Claude agent() for that reviewer, and the round is not recorded clean.
//   synthesisLeaf stays LOOP-OWNED (native Claude) even when the reviewer engine is external — the
//   panel's keep/drop judge is not a reviewer-persona dispatch, and the adapter's
//   parse_result(role_kind='review') only understands {findings:[...]}, not a synthesis {verdicts:[...]}
//   (b4 below asserts dispatchExternal is never called with a synthesis-shaped payload).
'use strict'
const assert = require('assert')

const sr = require('../showrunner.js')
const engineDispatchMod = require('../engine_dispatch.js')
const fs = require('fs')

// #129's reviewPanel persists a durable round-records.json (+ deferred-set.json) accumulator in the
// runDir. These scenarios use FIXED /tmp runDirs, so a stale accumulator from an earlier run of this
// very file would corrupt the next run's round-1 state (e.g. the blocking finding arrives pre-deferred
// and the fix dispatch never fires). Reset before every scenario for hermetic re-runs.
function freshRunDir(d) {
  fs.rmSync(d, { recursive: true, force: true })
  fs.mkdirSync(d, { recursive: true })
  return d
}

async function partA() {
  const calls = []
  const savedPrefs = globalThis.__SR_ENGINE_PREFS
  delete globalThis.__SR_ENGINE_PREFS

  globalThis.agent = async function (prompt, opts) {
    calls.push({ prompt, opts: opts || {}, label: (opts && opts.label) || '' })
    const label = (opts && opts.label) || ''
    // #118 fold: spec-gate + model-overrides ride the 'read startup state' courier, not a read-gate exec
    if (label === 'read startup state') return JSON.stringify({ ok: true, spec_gate: 'passed', model_overrides: {}, doc_dir: '' })
    if (label === 'exec') {
      if (typeof prompt === 'string' && prompt.includes('recover_entry.py')) {
        return [{ index: 0, ok: true, stdout: '{}' }]
      }
      if (typeof prompt === 'string' && prompt.includes('definition_doc.py read-gate')) {
        return [{ index: 0, ok: true, stdout: '{"review":"passed"}' }]
      }
      if (typeof prompt === 'string' && prompt.includes('engine_pref_load.py')) {
        return [{ index: 0, ok: true, stdout: '{"reviewer":"codex","implementation":"cursor","effort":{"review":"medium"}}' }]
      }
      return [{ index: 0, ok: true, stdout: '{}' }]
    }
    return null   // park everything else (workhorse, etc.)
  }
  globalThis.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))
  globalThis.log = () => {}

  try {
    await sr.showrunner({ workItem: 'wi-eng' })
  } catch (_) {
    // park or exception is fine; we only care that the engine-prefs exec fired
  }

  const epCall = calls.find(
    (c) => c.label === 'exec' && c.prompt.includes('engine_pref_load.py'),
  )
  assert.ok(epCall, 'FAIL (a1): startup did not issue an exec containing engine_pref_load.py')

  assert.deepStrictEqual(
    globalThis.__SR_ENGINE_PREFS,
    { reviewer: 'codex', implementation: 'cursor', effort: { review: 'medium' } },
    'FAIL (a2): __SR_ENGINE_PREFS does not deep-equal the parsed reviewer/implementation/effort map',
  )

  // fail-safe: bad/unreadable JSON -> both 'claude' + empty effort, never crashes.
  delete globalThis.__SR_ENGINE_PREFS
  calls.length = 0
  globalThis.agent = async function (prompt, opts) {
    const label = (opts && opts.label) || ''
    // #118 fold: spec-gate + model-overrides ride the 'read startup state' courier, not a read-gate exec
    if (label === 'read startup state') return JSON.stringify({ ok: true, spec_gate: 'passed', model_overrides: {}, doc_dir: '' })
    if (label === 'exec') {
      if (typeof prompt === 'string' && prompt.includes('engine_pref_load.py')) {
        return [{ index: 0, ok: false, stdout: 'not-json' }]
      }
      if (typeof prompt === 'string' && prompt.includes('recover_entry.py')) {
        return [{ index: 0, ok: true, stdout: '{}' }]
      }
      if (typeof prompt === 'string' && prompt.includes('definition_doc.py read-gate')) {
        return [{ index: 0, ok: true, stdout: '{"review":"passed"}' }]
      }
      return [{ index: 0, ok: true, stdout: '{}' }]
    }
    return null
  }
  try {
    await sr.showrunner({ workItem: 'wi-eng-fail' })
  } catch (_) {}
  assert.deepStrictEqual(
    globalThis.__SR_ENGINE_PREFS,
    { reviewer: 'claude', implementation: 'claude', effort: {} },
    'FAIL (a3): __SR_ENGINE_PREFS must fail-safe to both-claude + empty effort on a bad parse',
  )

  globalThis.__SR_ENGINE_PREFS = savedPrefs
  console.log('OK (a): startup plants __SR_ENGINE_PREFS (incl. effort sub-map) via exec(engine_pref_load.py); fail-safe both-claude+empty-effort on bad parse')
}

// ---------------------------------------------------------------------------
// PART B: reviewer engine branch (read-only) + UFR-7 fall-open + FR-15 mixed reviewer/impl split
// ---------------------------------------------------------------------------

function stubConfigVerifyGit(promptLog, synthesisCalls) {
  return async (prompt, opts) => {
    promptLog.push(prompt)
    const label = opts && opts.label
    if (label === 'lib' && prompt.includes('git -C')) return 'head-1\n'
    if (label === 'resume') return '1'
    if (label === 'lib' && prompt.includes('review_code_config.py')) {
      return { verifyCommand: 'python3 -m pytest targeted-tests -q', tiers: {} }
    }
    if (label && (label.startsWith('verify') || label === 'run verify')) {
      return { command: 'python3 -m pytest targeted-tests -q', returncode: 0, timedOut: false }
    }
    if (label && label.startsWith('synthesis')) {
      if (synthesisCalls) synthesisCalls.push({ prompt, opts })
      return { verdicts: [] }
    }
    if (label === 'lib' && prompt.includes('prov_entry.py')) return { ok: true }
    // #118 fold: the covers stamp is the 'stamp review coverage' courier (stdout text, not a lib object)
    if (label === 'stamp review coverage') return JSON.stringify({ ok: true })
    return null   // any native reviewer agent() call is asserted-against below, not stubbed here
  }
}

async function partB() {
  const savedDispatch = engineDispatchMod.dispatchExternal
  const savedPrefs = globalThis.__SR_ENGINE_PREFS

  // (b1) reviewer engine = codex, implementation = claude: reviewer routes external + read-only;
  // a Critical finding flows into the panel -> gate is changes-requested, not passed.
  globalThis.__SR_ENGINE_PREFS = { reviewer: 'codex', implementation: 'claude' }
  const dispatchCalls = []
  engineDispatchMod.dispatchExternal = async (o) => {
    dispatchCalls.push(o)
    if (o.roleKind === 'review') {
      return { findings: [{ file: 'p.py', line: 9, title: 'path traversal', severity: 'Critical', evidence: 'e' }] }
    }
    return { ok: false, reason: 'unreadable' }
  }

  let nativeReviewerFired = false
  const promptLog = []
  const synthesisCalls1 = []
  const base = stubConfigVerifyGit(promptLog, synthesisCalls1)
  global.agent = async (prompt, opts) => {
    const out = await base(prompt, opts)
    if (out !== null) return out
    const label = opts && opts.label
    if (label && /^(architecture|code|security|test|premortem)-reviewer/.test(label)) {
      nativeReviewerFired = true
      return { findings: [] }
    }
    return { findings: [] }
  }
  global.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))
  global.log = () => {}

  const r1 = await sr.reviewCodePhase('wi-eng-review', {
    worktree: '/tmp/build-worktree',
    expectedHead: 'head-1',
    runDir: freshRunDir('/tmp/showrunner-wi-eng-review-review-code-test-1'),
  })

  const reviewDispatch = dispatchCalls.filter((c) => c.roleKind === 'review')
  assert.ok(reviewDispatch.length > 0, 'FAIL (b1a): dispatchExternal was not called with roleKind:review')
  assert.ok(reviewDispatch.every((c) => c.engine === 'codex'), 'FAIL (b1a): review dispatch must use engine:codex')
  assert.strictEqual(nativeReviewerFired, false, 'FAIL (b1b): native reviewer agent() must NOT fire when the external review succeeds')
  assert.strictEqual(r1.gate, 'changes-requested', 'FAIL (b1c): the external Critical finding must flow into the panel (gate=changes-requested)')
  // synthesis stays loop-owned even with an external reviewer engine configured: it must run via the
  // native agent() (captured by the 'synthesis' label stub above) and dispatchExternal must never be
  // asked for a synthesis-shaped payload (dispatchCalls only ever carries roleKind:review/fix here).
  assert.ok(synthesisCalls1.length > 0, 'FAIL (b1d): synthesisLeaf must run via the native agent() (loop-owned) even when the reviewer engine is external')
  assert.ok(dispatchCalls.every((c) => c.roleKind === 'review' || c.roleKind === 'fix'),
    'FAIL (b1e): dispatchExternal must never be called for synthesis — only roleKind:review or roleKind:fix')

  // (b1f/g) depth-aware effort (FR-9): the deep reviewers (security/architecture — the reviewer-deep
  // tier) dispatch codex at xhigh; the regular reviewers (code/test/premortem) at high. roleKind stays
  // 'review' for all (asserted above); only the resolved effort differs by reviewer depth.
  const deepEfforts = reviewDispatch
    .filter((c) => /You are the (security|architecture)-reviewer\b/.test(c.prompt || ''))
    .map((c) => c.effort)
  const regularEfforts = reviewDispatch
    .filter((c) => /You are the (code|test|premortem)-reviewer\b/.test(c.prompt || ''))
    .map((c) => c.effort)
  assert.ok(deepEfforts.length > 0 && deepEfforts.every((e) => e === 'xhigh'),
    'FAIL (b1f): deep reviewers (security/architecture) must dispatch codex at effort xhigh')
  assert.ok(regularEfforts.length > 0 && regularEfforts.every((e) => e === 'high'),
    'FAIL (b1g): regular reviewers (code/test/premortem) must dispatch codex at effort high')

  // (b2) UFR-7: dispatchExternal for roleKind:review returns unreadable -> the native reviewer agent()
  // fires for that reviewer as the fall-open path, and the round is not recorded clean.
  dispatchCalls.length = 0
  nativeReviewerFired = false
  const promptLog2 = []
  const base2 = stubConfigVerifyGit(promptLog2)
  engineDispatchMod.dispatchExternal = async (o) => {
    dispatchCalls.push(o)
    if (o.roleKind === 'review') return { ok: false, reason: 'unreadable' }
    return { ok: false, reason: 'unreadable' }
  }
  global.agent = async (prompt, opts) => {
    const out = await base2(prompt, opts)
    if (out !== null) return out
    const label = opts && opts.label
    if (label && /^(architecture|code|security|test|premortem)-reviewer/.test(label)) {
      nativeReviewerFired = true
      return { findings: [] }
    }
    return { findings: [] }
  }

  const r2 = await sr.reviewCodePhase('wi-eng-ufr7', {
    worktree: '/tmp/build-worktree',
    expectedHead: 'head-1',
    runDir: freshRunDir('/tmp/showrunner-wi-eng-ufr7-review-code-test-1'),
  })
  assert.ok(dispatchCalls.some((c) => c.roleKind === 'review'), 'FAIL (b2a): dispatchExternal must still be attempted for roleKind:review')
  assert.strictEqual(nativeReviewerFired, true, 'FAIL (b2b): UFR-7 unreadable external review must fall open to the native reviewer agent()')
  assert.strictEqual(r2.gate, 'passed', 'FAIL (b2c): a clean fall-open round (no findings from either path) is recorded clean')

  // (b3) FR-15 mixed reviewer=codex / implementation=cursor: reviewer dispatch uses engine:codex,
  // roleKind:review; fixStep's dispatch uses engine:cursor, roleKind:fix. Force a blocking finding
  // from the (external) reviewer so fixStep actually runs, and let the external fix succeed so the
  // native fixer agent() never fires (proving the write path is on the implementation engine only).
  globalThis.__SR_ENGINE_PREFS = { reviewer: 'codex', implementation: 'cursor' }
  dispatchCalls.length = 0
  let nativeFixerFired = false
  let round = 0
  const promptLog3 = []
  const synthesisCalls3 = []
  const base3 = stubConfigVerifyGit(promptLog3, synthesisCalls3)
  engineDispatchMod.dispatchExternal = async (o) => {
    dispatchCalls.push(o)
    if (o.roleKind === 'review') {
      round += 1
      if (round === 1) {
        return { findings: [{ file: 'p.py', line: 1, title: 'blocking issue', severity: 'Critical', evidence: 'e' }] }
      }
      return { findings: [] }   // round 2+: clean after the (simulated) external fix
    }
    if (o.roleKind === 'fix') {
      return { ok: true, signal: 'ok', evidence: {} }
    }
    return { ok: false, reason: 'unreadable' }
  }
  global.agent = async (prompt, opts) => {
    const out = await base3(prompt, opts)
    if (out !== null) return out
    const label = opts && opts.label
    if (label && /^(architecture|code|security|test|premortem)-reviewer/.test(label)) {
      return { findings: [] }
    }
    if (label === 'code-fixer') {
      nativeFixerFired = true
      return { fixed: [], deferred: [] }
    }
    return { findings: [] }
  }

  const r3 = await sr.reviewCodePhase('wi-eng-mixed', {
    worktree: '/tmp/build-worktree',
    expectedHead: 'head-1',
    runDir: freshRunDir('/tmp/showrunner-wi-eng-mixed-review-code-test-1'),
  })
  const reviewDispatch3 = dispatchCalls.filter((c) => c.roleKind === 'review')
  const fixDispatch3 = dispatchCalls.filter((c) => c.roleKind === 'fix')
  assert.ok(reviewDispatch3.length > 0 && reviewDispatch3.every((c) => c.engine === 'codex'),
    'FAIL (b3a): reviewer dispatch must use engine:codex, roleKind:review')
  assert.ok(fixDispatch3.length > 0 && fixDispatch3.every((c) => c.engine === 'cursor'),
    'FAIL (b3b): fixStep dispatch must use engine:cursor, roleKind:fix (FR-15 split)')
  assert.strictEqual(nativeFixerFired, false, 'FAIL (b3c): the native code-fixer agent() must not fire when the external fix succeeds')
  assert.strictEqual(r3.gate, 'passed', 'FAIL (b3d): a successfully-fixed round advances to passed')
  // synthesis stays loop-owned (native agent()) even under a mixed reviewer=codex/implementation=cursor
  // configuration; dispatchExternal in this scenario only ever carries roleKind:review or roleKind:fix.
  assert.ok(synthesisCalls3.length > 0, 'FAIL (b3e): synthesisLeaf must run via the native agent() (loop-owned) under mixed external engines')
  assert.ok(dispatchCalls.every((c) => c.roleKind === 'review' || c.roleKind === 'fix'),
    'FAIL (b3f): dispatchExternal must never be called for synthesis under mixed external engines')

  engineDispatchMod.dispatchExternal = savedDispatch
  globalThis.__SR_ENGINE_PREFS = savedPrefs
  console.log('OK (b): reviewer read-only on reviewer engine (Critical flows) + UFR-7 re-run on Claude + mixed reviewer!=impl (FR-15 split) + synthesis stays loop-owned')
}

;(async () => {
  await partA()
  await partB()
  console.log('OK: Task 12 — reviewCodeLeaves engine branch + startup __SR_ENGINE_PREFS load')
})().catch((e) => { console.error('FAIL:', e.message || e, e.stack); process.exit(1) })
