// plugins/superheroes/lib/tests/showrunner_engine_author_smoke.js
// The author-plan external-dispatch path (plan-author engine route): write-SANDBOXED but
// commit-free — no preSHA capture, no engine_adapter commit; the model tier short name is
// threaded into build-argv (--model) so cursor can map it (fable -> its fable model id);
// notify rides back to the caller; the journal append stays UFR-6-gated (fail-closed).
// Then the producePhase wiring: ONLY the plan doc consults enginePreferences.planAuthor
// (tasks always authors native), and a failed external dispatch falls open to the native
// author within the same attempt.
const assert = require('assert')
const logs = []
global.log = (m) => logs.push(m)
global.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))

// Route an agent() call by exact label, then prompt substring (the dispatch-smoke idiom).
function makeAgent(routes) {
  return async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    for (const [needle, resp] of routes) if (label === needle) return typeof resp === 'function' ? resp(prompt) : resp
    for (const [needle, resp] of routes) if (prompt.includes(needle)) return typeof resp === 'function' ? resp(prompt) : resp
    return ''
  }
}

async function dispatchSmokes() {
  const d = require('../engine_dispatch.js')

  // Happy path: ok + notify, no preSHA, no commit, --model threaded.
  const execLogA = []
  global.agent = makeAgent([
    ['exec', (prompt) => {
      execLogA.push(prompt)
      if (prompt.includes('engine_adapter.py build-argv')) {
        return [{ index: 0, ok: true, stdout: JSON.stringify(
          ['cursor-agent', '--model', 'claude-fable-5-thinking-xhigh', '-p', '--trust', '-f', '--output-format', 'stream-json']) }]
      }
      if (prompt.includes('engine_adapter.py parse-result')) {
        return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true, notify: [{ identity: 'n1', message: 'took a default' }] }) }]
      }
      if (prompt.includes('journal_entry.py')) {
        return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
      }
      if (prompt.includes('cursor-agent')) {
        return [{ index: 0, ok: true, stdout: '{"status":"ok"}' }]
      }
      return [{ index: 0, ok: true, stdout: '{}' }]
    }],
  ])
  const rA = await d.dispatchExternal({ engine: 'cursor', roleKind: 'author-plan', effort: 'composer',
    prompt: 'author the plan', cwd: '/repo', schema: {}, timeoutSeconds: 300, workItem: 'wi-plan', model: 'fable' })
  assert.strictEqual(rA.ok, true, 'author-plan happy path returns ok')
  assert.deepStrictEqual(rA.notify, [{ identity: 'n1', message: 'took a default' }], 'notify rides back')
  const runCmd = execLogA.find((c) => c.includes('cursor-agent') && c.includes(' < '))
  assert.ok(runCmd && /\.prompt/.test(runCmd), 'author-plan must run cursor-agent with the staged prompt on stdin')
  assert.ok(!execLogA.some((c) => c.includes('git') && c.includes('rev-parse HEAD')), 'author-plan captures no preSHA')
  assert.ok(!execLogA.some((c) => c.includes('engine_adapter.py commit')), 'author-plan never commits')
  const argvCmd = execLogA.find((c) => c.includes('engine_adapter.py build-argv'))
  assert.ok(argvCmd.includes("--model 'fable'"), 'model tier short name is threaded into build-argv: ' + argvCmd)
  assert.ok(execLogA.some((c) => c.includes('journal_entry.py')), 'author-plan dispatch is journaled')

  // UFR-6: a failed journal append fails the author-plan dispatch closed (unauditable).
  global.agent = makeAgent([
    ['exec', (prompt) => {
      if (prompt.includes('engine_adapter.py build-argv')) {
        return [{ index: 0, ok: true, stdout: JSON.stringify(['cursor-agent', '-p', '--trust', '-f']) }]
      }
      if (prompt.includes('engine_adapter.py parse-result')) {
        return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true, notify: [] }) }]
      }
      if (prompt.includes('journal_entry.py')) {
        return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: false }) }]
      }
      if (prompt.includes('cursor-agent')) return [{ index: 0, ok: true, stdout: '{"status":"ok"}' }]
      return [{ index: 0, ok: true, stdout: '{}' }]
    }],
  ])
  const rA2 = await d.dispatchExternal({ engine: 'cursor', roleKind: 'author-plan', effort: 'composer',
    prompt: 'author the plan', cwd: '/repo', schema: {}, timeoutSeconds: 300, workItem: 'wi-plan', model: 'fable' })
  assert.strictEqual(rA2.ok, false, 'author-plan fails closed on a failed journal append')
  assert.strictEqual(rA2.reason, 'unauditable', 'author-plan UFR-6 reason is unauditable')

  console.log('OK: engine_dispatch author-plan path (commit-free write, model threading, notify, UFR-6)')
}

// ---------------------------------------------------------------------------
// producePhase wiring: planAuthor engine route is plan-only + falls open to native.
// ---------------------------------------------------------------------------
const USABLE_SIGNAL = JSON.stringify({ usable: true, recorded: 'abc123', expected: 'abc123' })
const NOT_USABLE_SIGNAL = JSON.stringify({ usable: false, recorded: '', expected: '' })
// Content complete but marker not yet stamped (external path pre-stamp check).
const CONTENT_READY_SIGNAL = JSON.stringify(
  { usable: false, recorded: '', expected: 'abc123', missing_sections: [], placeholder: false })

// Agent stub for producePhase: emit-signals sequence + external dispatch stubs + native author trap.
function produceAgent({ usableSeq, externalOk, externalRuns = [], nativeAuthorCalls = [], notifyLedger = [],
  events = [], gitSnapshots = null, strayPath = null, untrackedStray = false, preExistingDirty = null,
  revertPrompts = [], resetPrompts = [], writeMarkerPrompts = [] }) {
  const seq = usableSeq.slice()
  let gitSnapIdx = 0
  const gitSeq = gitSnapshots || ['', '']
  return async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    if (opts && opts.courier) {
      const execLabel = (opts && opts.label) || ''
      if (prompt.includes('emit-signals')) {
        const next = seq.shift()
        const stdout = (typeof next === 'string') ? next : (next ? USABLE_SIGNAL : NOT_USABLE_SIGNAL)
        return [{ index: 0, ok: true, stdout }]
      }
      if (prompt.includes('append-notify')) {
        const m = prompt.match(/--entries\s+'([^']+)'/)
        if (m) { try { notifyLedger.push(...JSON.parse(m[1])) } catch (_) {} }
        return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
      }
      if (execLabel === 'author-plan git snapshot' || prompt.includes('git status --porcelain')) {
        events.push('git-snapshot')
        if (gitSnapshots) {
          const raw = gitSeq[gitSnapIdx++]
          if (raw === null) return [{ index: 0, ok: false, stdout: '' }]   // simulated courier flake
          return [{ index: 0, ok: true, stdout: raw ?? '' }]
        }
        const snapIdx = gitSnapIdx++
        if (snapIdx === 0 && preExistingDirty) return [{ index: 0, ok: true, stdout: preExistingDirty }]
        if (snapIdx === 1 && strayPath) {
          const prefix = untrackedStray ? '?? ' : ' M '
          return [{ index: 0, ok: true, stdout: `${prefix}${strayPath}` }]
        }
        return [{ index: 0, ok: true, stdout: '' }]
      }
      if (execLabel === 'author-plan revert strays') {
        events.push('revert-strays')
        revertPrompts.push(prompt)
        const n = (prompt.match(/^\d+\./gm) || ['1.']).length
        return Array.from({ length: n }, (_, i) => ({ index: i, ok: true, stdout: '' }))
      }
      if (execLabel === 'reset author-plan draft') {
        events.push('reset')
        resetPrompts.push(prompt)
        return [{ index: 0, ok: true, stdout: '' }]
      }
      if (execLabel === 'author-plan write marker' || (prompt.includes('front_half_usable.py') && prompt.includes('--write-marker'))) {
        events.push('write-marker')
        writeMarkerPrompts.push(prompt)
        return [{ index: 0, ok: true, stdout: JSON.stringify({ wrote: true }) }]
      }
      if (prompt.includes('engine_adapter.py build-argv')) {
        externalRuns.push(prompt)
        return [{ index: 0, ok: true, stdout: JSON.stringify(['cursor-agent', '-p', '--trust', '-f']) }]
      }
      if (prompt.includes('engine_adapter.py parse-result')) {
        return [{ index: 0, ok: true, stdout: JSON.stringify(
          externalOk ? { ok: true, notify: [{ identity: 'n-ext', message: 'external default' }] }
            : { ok: false, reason: 'unreadable' }) }]
      }
      if (prompt.includes('journal_entry.py')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
      if (prompt.includes('cursor-agent')) return [{ index: 0, ok: true, stdout: '{"status":"ok"}' }]
      return [{ index: 0, ok: true, stdout: '' }, { index: 1, ok: true, stdout: '' }]
    }
    if (label === 'lib') return { ok: true }
    if (label.startsWith('author-')) { events.push('native'); nativeAuthorCalls.push(prompt); return { status: 'ok' } }
    return null
  }
}

async function produceSmokes() {
  const sr = require('../showrunner.js')
  const savedPrefs = globalThis.__SR_ENGINE_PREFS
  const savedOverrides = globalThis.__SR_OVERRIDES
  try {
    globalThis.__SR_ENGINE_PREFS = { reviewer: 'claude', implementation: 'claude', planAuthor: 'cursor', effort: {} }
    globalThis.__SR_OVERRIDES = { 'author-plan': 'fable' }

    // (1) plan doc + planAuthor:cursor + external ok -> external authored, native author NOT called.
    let externalRuns = [], nativeCalls = [], notifyLedger = [], events = [], writeMarkerPrompts = []
    global.agent = produceAgent({ usableSeq: [false, CONTENT_READY_SIGNAL, USABLE_SIGNAL, USABLE_SIGNAL],
      externalOk: true, externalRuns, nativeAuthorCalls: nativeCalls, notifyLedger, events, writeMarkerPrompts })
    let r = await sr.producePhase('plan', 'wi-ext')
    assert.strictEqual(r.confidence, 'high', '(1) external author + usable -> high')
    assert.strictEqual(externalRuns.length, 1, '(1) exactly one external dispatch')
    assert.strictEqual(nativeCalls.length, 0, '(1) native author is NOT dispatched when external succeeds')
    assert.ok(externalRuns[0].includes("--role 'author-plan'"), '(1) dispatch carries the author-plan role')
    assert.ok(externalRuns[0].includes("--model 'fable'"), '(1) dispatch threads the resolved author-plan tier: ' + externalRuns[0])
    assert.ok(!externalRuns[0].includes('--write-marker'),
      '(1) external author prompt must NOT include --write-marker')
    assert.ok(events.includes('write-marker'), '(1) showrunner stamps marker after confinement')
    assert.ok(events.indexOf('write-marker') > events.lastIndexOf('git-snapshot'),
      '(1) write-marker exec runs AFTER confinement git snapshots')
    assert.ok(writeMarkerPrompts.length === 1, '(1) exactly one showrunner write-marker exec')
    assert.ok(writeMarkerPrompts[0].includes('--write-marker'),
      '(1) showrunner write-marker exec uses front_half_usable.py --write-marker')
    assert.ok(notifyLedger.some((n) => n.phase === 'plan' && n.identity === 'n-ext' && n.message === 'external default'),
      '(1) external notify is durably recorded via append-notify')

    // (2) tasks doc NEVER consults planAuthor -> native author even with the pref set.
    externalRuns = []; nativeCalls = []
    global.agent = produceAgent({ usableSeq: [false, true], externalOk: true, externalRuns, nativeAuthorCalls: nativeCalls })
    r = await sr.producePhase('tasks', 'wi-tasks')
    assert.strictEqual(r.confidence, 'high', '(2) tasks authored -> high')
    assert.strictEqual(externalRuns.length, 0, '(2) tasks never routes to the external engine')
    assert.strictEqual(nativeCalls.length, 1, '(2) tasks authors native')

    // (3) external dispatch fails -> falls open to the native author within the same attempt.
    externalRuns = []; nativeCalls = []; events = []; const resetPrompts3 = []
    global.agent = produceAgent({ usableSeq: [false, true, true], externalOk: false, externalRuns, nativeAuthorCalls: nativeCalls, events, resetPrompts: resetPrompts3 })
    r = await sr.producePhase('plan', 'wi-fallopen')
    assert.strictEqual(r.confidence, 'high', '(3) fall-open native author + usable -> high')
    assert.strictEqual(externalRuns.length, 1, '(3) external was attempted once')
    assert.strictEqual(nativeCalls.length, 1, '(3) native author ran after the external failure (fall-open)')
    assert.ok(events.indexOf('reset') >= 0 && events.indexOf('native') >= 0, '(3) reset and native both ran')
    assert.ok(events.indexOf('reset') < events.indexOf('native'), '(3) reset author-plan draft before native author')
    assert.ok(resetPrompts3.some((p) => p.includes('docs/superheroes/wi-fallopen/plan.md')),
      '(3) reset removes plan.md')
    assert.ok(resetPrompts3.some((p) => p.includes('docs/superheroes/wi-fallopen/.plan.complete')),
      '(3) reset removes .plan.complete')

    // (5) stray checkout edit on external success -> reverted + native fallback within the same attempt.
    externalRuns = []; nativeCalls = []; events = []; const revertPrompts5 = []; const resetPrompts5 = []
    global.agent = produceAgent({ usableSeq: [false, true, true], externalOk: true, externalRuns, nativeAuthorCalls: nativeCalls, events, strayPath: 'README.md', revertPrompts: revertPrompts5, resetPrompts: resetPrompts5 })
    r = await sr.producePhase('plan', 'wi-stray')
    assert.strictEqual(r.confidence, 'high', '(5) stray edit triggers native fallback + usable -> high')
    assert.strictEqual(externalRuns.length, 1, '(5) external was attempted once')
    assert.strictEqual(nativeCalls.length, 1, '(5) native author ran after stray revert')
    assert.ok(events.includes('revert-strays'), '(5) stray paths were reverted')
    assert.ok(revertPrompts5.some((p) => p.includes("git checkout -- 'README.md'")),
      '(5) tracked stray reverted via git checkout: ' + revertPrompts5.join(' | '))
    assert.ok(resetPrompts5.some((p) => p.includes('docs/superheroes/wi-stray/plan.md')),
      '(5) reset removes plan.md after stray revert')
    assert.ok(resetPrompts5.some((p) => p.includes('docs/superheroes/wi-stray/.plan.complete')),
      '(5) reset removes .plan.complete after stray revert')
    assert.ok(events.indexOf('reset') < events.indexOf('native'), '(5) reset before native after stray edit')
    assert.ok(!events.includes('write-marker'), '(5) write-marker NOT stamped when confinement fails')

    // (5b) untracked stray -> rm -rf -- and native fallback.
    externalRuns = []; nativeCalls = []; events = []; const revertPrompts5b = []
    global.agent = produceAgent({ usableSeq: [false, true, true], externalOk: true, externalRuns, nativeAuthorCalls: nativeCalls, events, strayPath: 'scratch.txt', untrackedStray: true, revertPrompts: revertPrompts5b })
    r = await sr.producePhase('plan', 'wi-untracked-stray')
    assert.strictEqual(r.confidence, 'high', '(5b) untracked stray triggers native fallback + usable -> high')
    assert.ok(revertPrompts5b.some((p) => p.includes("rm -rf -- 'scratch.txt'")),
      '(5b) untracked stray removed via rm -rf --: ' + revertPrompts5b.join(' | '))

    // (6) pre-existing dirty file outside doc dir is left untouched on external success.
    externalRuns = []; nativeCalls = []; events = []
    global.agent = produceAgent({ usableSeq: [false, CONTENT_READY_SIGNAL, USABLE_SIGNAL, USABLE_SIGNAL],
      externalOk: true, externalRuns, nativeAuthorCalls: nativeCalls, events,
      preExistingDirty: ' M README.md' })
    r = await sr.producePhase('plan', 'wi-predirty')
    assert.strictEqual(r.confidence, 'high', '(6) pre-existing dirty + external usable -> high')
    assert.strictEqual(externalRuns.length, 1, '(6) external dispatch ran')
    assert.strictEqual(nativeCalls.length, 0, '(6) native author NOT called when no new strays')
    assert.ok(!events.includes('revert-strays'), '(6) pre-existing dirty file was not reverted')

    // (7) external ok but unusable draft -> native fallback within the same attempt (not 3 external retries).
    externalRuns = []; nativeCalls = []; events = []; const resetPrompts7 = []
    global.agent = produceAgent({ usableSeq: [false, NOT_USABLE_SIGNAL, true, true], externalOk: true, externalRuns, nativeAuthorCalls: nativeCalls, events, resetPrompts: resetPrompts7 })
    r = await sr.producePhase('plan', 'wi-unusable-ext')
    assert.strictEqual(r.confidence, 'high', '(7) unusable external draft falls open to native -> high')
    assert.strictEqual(externalRuns.length, 1, '(7) only one external attempt before native fallback')
    assert.strictEqual(nativeCalls.length, 1, '(7) native author ran after unusable external draft')
    assert.ok(events.indexOf('reset') < events.indexOf('native'), '(7) reset before native after unusable external draft')
    assert.ok(resetPrompts7.some((p) => p.includes('docs/superheroes/wi-unusable-ext/plan.md')),
      '(7) reset removes plan.md after unusable external draft')
    assert.ok(resetPrompts7.some((p) => p.includes('docs/superheroes/wi-unusable-ext/.plan.complete')),
      '(7) reset removes .plan.complete after unusable external draft')
    assert.ok(!events.includes('write-marker'), '(7) write-marker NOT stamped when external content unusable')

    // (8) FAILED before-snapshot (courier flake) + pre-existing dirty checkout: revert NOTHING
    // (an empty "before" would make the user's own edits look stray), discard the draft, native fallback.
    externalRuns = []; nativeCalls = []; events = []
    global.agent = produceAgent({ usableSeq: [false, true], externalOk: true, externalRuns,
      nativeAuthorCalls: nativeCalls, events, gitSnapshots: [null, ' M user-own-edit.txt'] })
    r = await sr.producePhase('plan', 'wi-snap-flake')
    assert.strictEqual(r.confidence, 'high', '(8) unconfinable dispatch falls open to native -> high')
    assert.ok(!events.includes('revert-strays'), '(8) NOTHING is reverted when the before-snapshot failed')
    assert.ok(events.includes('reset'), '(8) external draft is discarded when unconfinable')
    assert.strictEqual(nativeCalls.length, 1, '(8) native author ran after unconfinable dispatch')

    // (4) planAuthor absent/claude -> plan authors native, no external dispatch.
    globalThis.__SR_ENGINE_PREFS = { reviewer: 'claude', implementation: 'claude', effort: {} }
    externalRuns = []; nativeCalls = []
    global.agent = produceAgent({ usableSeq: [false, true], externalOk: true, externalRuns, nativeAuthorCalls: nativeCalls })
    r = await sr.producePhase('plan', 'wi-native')
    assert.strictEqual(r.confidence, 'high', '(4) native plan author -> high')
    assert.strictEqual(externalRuns.length, 0, '(4) no external dispatch without planAuthor')
    assert.strictEqual(nativeCalls.length, 1, '(4) native author ran')

    // (9) external author-plan dispatch cwd follows __SR_ROOT when process cwd fallback is '.'.
    globalThis.__SR_ENGINE_PREFS = { reviewer: 'claude', implementation: 'claude', planAuthor: 'cursor', effort: {} }
    const savedRoot9 = globalThis.__SR_ROOT
    const savedProcess9 = global.process
    try {
      globalThis.__SR_ROOT = '/test-checkout-root'
      global.process = undefined
      externalRuns = []; nativeCalls = []
      global.agent = produceAgent({ usableSeq: [false, CONTENT_READY_SIGNAL, USABLE_SIGNAL, USABLE_SIGNAL],
        externalOk: true, externalRuns, nativeAuthorCalls: nativeCalls })
      r = await sr.producePhase('plan', 'wi-cwd-root')
      assert.strictEqual(r.confidence, 'high', '(9) external author at checkout root -> high')
      assert.strictEqual(externalRuns.length, 1, '(9) one external dispatch')
      assert.ok(externalRuns[0].includes("--cwd '/test-checkout-root'"),
        '(9) dispatch cwd is checkoutRoot when process absent: ' + externalRuns[0])
    } finally {
      globalThis.__SR_ROOT = savedRoot9
      global.process = savedProcess9
    }

    console.log('OK: producePhase planAuthor route (plan-only, fall-open, native default)')
  } finally {
    globalThis.__SR_ENGINE_PREFS = savedPrefs
    globalThis.__SR_OVERRIDES = savedOverrides
  }
}

async function main() {
  await dispatchSmokes()
  await produceSmokes()
}
main().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
