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

// Agent stub for producePhase: emit-signals sequence + external dispatch stubs + native author trap.
function produceAgent({ usableSeq, externalOk, externalRuns = [], nativeAuthorCalls = [] }) {
  const seq = usableSeq.slice()
  return async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    if (opts && opts.courier) {
      if (prompt.includes('emit-signals')) {
        return [{ index: 0, ok: true, stdout: seq.shift() ? USABLE_SIGNAL : NOT_USABLE_SIGNAL }]
      }
      if (prompt.includes('append-notify')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
      if (prompt.includes('engine_adapter.py build-argv')) {
        externalRuns.push(prompt)
        return [{ index: 0, ok: true, stdout: JSON.stringify(['cursor-agent', '-p', '--trust', '-f']) }]
      }
      if (prompt.includes('engine_adapter.py parse-result')) {
        return [{ index: 0, ok: true, stdout: JSON.stringify(
          externalOk ? { ok: true, notify: [] } : { ok: false, reason: 'unreadable' }) }]
      }
      if (prompt.includes('journal_entry.py')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
      if (prompt.includes('cursor-agent')) return [{ index: 0, ok: true, stdout: '{"status":"ok"}' }]
      return [{ index: 0, ok: true, stdout: '' }, { index: 1, ok: true, stdout: '' }]
    }
    if (label === 'lib') return { ok: true }
    if (label.startsWith('author-')) { nativeAuthorCalls.push(prompt); return { status: 'ok' } }
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
    let externalRuns = [], nativeCalls = []
    global.agent = produceAgent({ usableSeq: [false, true], externalOk: true, externalRuns, nativeAuthorCalls: nativeCalls })
    let r = await sr.producePhase('plan', 'wi-ext')
    assert.strictEqual(r.confidence, 'high', '(1) external author + usable -> high')
    assert.strictEqual(externalRuns.length, 1, '(1) exactly one external dispatch')
    assert.strictEqual(nativeCalls.length, 0, '(1) native author is NOT dispatched when external succeeds')
    assert.ok(externalRuns[0].includes("--role 'author-plan'"), '(1) dispatch carries the author-plan role')
    assert.ok(externalRuns[0].includes("--model 'fable'"), '(1) dispatch threads the resolved author-plan tier: ' + externalRuns[0])

    // (2) tasks doc NEVER consults planAuthor -> native author even with the pref set.
    externalRuns = []; nativeCalls = []
    global.agent = produceAgent({ usableSeq: [false, true], externalOk: true, externalRuns, nativeAuthorCalls: nativeCalls })
    r = await sr.producePhase('tasks', 'wi-tasks')
    assert.strictEqual(r.confidence, 'high', '(2) tasks authored -> high')
    assert.strictEqual(externalRuns.length, 0, '(2) tasks never routes to the external engine')
    assert.strictEqual(nativeCalls.length, 1, '(2) tasks authors native')

    // (3) external dispatch fails -> falls open to the native author within the same attempt.
    externalRuns = []; nativeCalls = []
    global.agent = produceAgent({ usableSeq: [false, true], externalOk: false, externalRuns, nativeAuthorCalls: nativeCalls })
    r = await sr.producePhase('plan', 'wi-fallopen')
    assert.strictEqual(r.confidence, 'high', '(3) fall-open native author + usable -> high')
    assert.strictEqual(externalRuns.length, 1, '(3) external was attempted once')
    assert.strictEqual(nativeCalls.length, 1, '(3) native author ran after the external failure (fall-open)')

    // (4) planAuthor absent/claude -> plan authors native, no external dispatch.
    globalThis.__SR_ENGINE_PREFS = { reviewer: 'claude', implementation: 'claude', effort: {} }
    externalRuns = []; nativeCalls = []
    global.agent = produceAgent({ usableSeq: [false, true], externalOk: true, externalRuns, nativeAuthorCalls: nativeCalls })
    r = await sr.producePhase('plan', 'wi-native')
    assert.strictEqual(r.confidence, 'high', '(4) native plan author -> high')
    assert.strictEqual(externalRuns.length, 0, '(4) no external dispatch without planAuthor')
    assert.strictEqual(nativeCalls.length, 1, '(4) native author ran')

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
