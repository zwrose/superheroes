// plugins/superheroes/lib/tests/showrunner_engine_confinement_tripwire_smoke.js
// #355: the post-dispatch primary-repo confinement tripwire. An external engine subprocess is
// dispatched cd'd into a disposable build worktree, but worktree confinement does NOT bind the
// spawned CLI's children — the enforcer's PreToolUse hook governs OUR agents' Bash, not a
// `--trust -f` engine's grandchildren (live 2026-07-10: a cursor fix leaf committed to the PRIMARY
// checkout's main, then self-reverted). This smoke pins the mechanical tripwire: snapshot the PRIMARY
// repo (globalThis.__SR_ROOT) HEAD-reflog / HEAD-sha / porcelain-status BEFORE the CLI runs and AFTER
// it settles, and on ANY out-of-worktree delta journal a first-class `confinement_tripwire` event +
// raise a distinct narrator notice. The reflog signal is the load-bearing one: it is append-only, so
// a commit-and-self-revert excursion (the observed shape, end-state clean) still grows the reflog and
// is caught where a bare HEAD/status probe would read clean.
const assert = require('assert')
const { markedStdout } = require('./_marked_stdout.js')

// Build the dispatch exec stub. `tripStates` is the ORDERED list of __SR_TRIP__ probe stdout lines the
// primary-repo probe returns (call 0 = pre-snapshot, call 1 = post-snapshot); a null element makes that
// probe call return an UNPARSEABLE stdout (ok but no sentinel). execLog captures every agent prompt.
function makeWriteStub(execLog, tripStates) {
  let tripCall = 0
  return async (prompt) => {
    execLog.push(prompt)
    // The CLI-run leaf rides the hardened marker courier (not the plain exec dumb-pipe), so it must
    // answer with a MARKER-carrying string; route it FIRST by the argv + perl-guard signature.
    if ((prompt.includes('cursor-agent') || prompt.includes('--trust')) && prompt.includes('perl -e')) {
      return markedStdout('{"raw":"external build output"}')
    }
    if (prompt.includes('__SR_TRIP__')) {
      const state = tripStates[tripCall]
      tripCall += 1
      if (state == null) return [{ index: 0, ok: true, stdout: 'garbled-no-sentinel\n' }]
      return [{ index: 0, ok: true, stdout: state }]
    }
    if (prompt.includes('git') && prompt.includes('rev-parse HEAD')) return [{ index: 0, ok: true, stdout: 'preSHA-abc\n' }]
    if (prompt.includes('engine_adapter.py build-argv')) {
      return [{ index: 0, ok: true, stdout: JSON.stringify(['cursor-agent', '--model', 'composer-2.5-fast', '-p', '--trust', '-f']) }]
    }
    if (prompt.includes('engine_adapter.py parse-result')) {
      return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true, signal: 'ok', evidence: {} }) }]
    }
    if (prompt.includes('engine_adapter.py commit')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true, sha: 'newsha' }) }]
    if (prompt.includes('journal_entry.py')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
    return [{ index: 0, ok: true, stdout: '{}' }]
  }
}

function tripJournals(execLog) {
  return execLog.filter((c) => c.includes('journal_entry.py') && c.includes('--event-type confinement_tripwire'))
}
function probeCmds(execLog) {
  return execLog.filter((c) => c.includes('__SR_TRIP__'))
}

;(async () => {
  const d = require('../engine_dispatch.js')

  // -------------------------------------------------------------------
  // Case A: a commit-and-self-revert excursion on the PRIMARY repo grows the HEAD reflog even though the
  // end state is clean (same HEAD sha, clean tree). The append-only reflog signal catches it.
  // -------------------------------------------------------------------
  {
    const logs = []
    global.log = (m) => logs.push(m)
    const execLog = []
    // pre: reflog 5 / head abc / status 0 ; post: reflog 7 (commit + reset) / head abc (reverted) / status 0
    global.agent = makeWriteStub(execLog, ['__SR_TRIP__ 5 abc 0\n', '__SR_TRIP__ 7 abc 0\n'])
    const saved = globalThis.__SR_ROOT
    globalThis.__SR_ROOT = '/primary'
    try {
      const r = await d.dispatchExternal({ engine: 'cursor', roleKind: 'fix', effort: 'high', prompt: 'fix',
        cwd: '/tmp/wt', schema: {}, timeoutSeconds: 300, taskId: 'T1', workItem: 'wi-abc' })
      // Detection is ORTHOGONAL to the dispatch outcome — a clean in-worktree commit still succeeded.
      assert.strictEqual(r.ok, true, 'A: the dispatch itself still returns its native success shape')
      // Two probes fired against the PRIMARY root (pre + post), each targeting /primary, not the worktree.
      const probes = probeCmds(execLog)
      assert.strictEqual(probes.length, 2, 'A: exactly one pre + one post primary-repo probe: ' + probes.length)
      assert.ok(probes.every((c) => c.includes("git -C '/primary'")), 'A: the probe targets the PRIMARY root, not the build worktree')
      assert.ok(probes.every((c) => c.includes('reflog show HEAD') && c.includes('status --porcelain')),
        'A: the probe reads BOTH the append-only HEAD reflog and the porcelain status')
      // A first-class confinement_tripwire journal event was written naming the reflog signal + root.
      const tj = tripJournals(execLog)
      assert.strictEqual(tj.length, 1, 'A: exactly one confinement_tripwire journal event: ' + tj.length)
      const payload = JSON.parse(tj[0].match(/--payload '(.*)'$/s)[1])
      assert.ok(Array.isArray(payload.confinementBreach) && payload.confinementBreach.includes('primary-HEAD-reflog-grew'),
        'A: the journal names the reflog-growth signal: ' + JSON.stringify(payload.confinementBreach))
      assert.strictEqual(payload.confinementRoot, '/primary', 'A: the journal names the primary root probed')
      // A distinct narrator notice fired (run_watch surfaces it live).
      assert.ok(logs.some((m) => m.includes('CONFINEMENT-BREACH') && m.includes('primary-HEAD-reflog-grew')),
        'A: a distinct CONFINEMENT-BREACH narrator notice named the signal')
      console.log('OK: #355 tripwire fires on a reflog-growth (commit + self-revert) excursion')
    } finally { globalThis.__SR_ROOT = saved }
  }

  // -------------------------------------------------------------------
  // Case B: identical pre/post snapshots (the engine stayed confined) -> SILENT (no journal, no notice).
  // -------------------------------------------------------------------
  {
    const logs = []
    global.log = (m) => logs.push(m)
    const execLog = []
    global.agent = makeWriteStub(execLog, ['__SR_TRIP__ 5 abc 0\n', '__SR_TRIP__ 5 abc 0\n'])
    const saved = globalThis.__SR_ROOT
    globalThis.__SR_ROOT = '/primary'
    try {
      const r = await d.dispatchExternal({ engine: 'cursor', roleKind: 'fix', effort: 'high', prompt: 'fix',
        cwd: '/tmp/wt', schema: {}, timeoutSeconds: 300, taskId: 'T1', workItem: 'wi-abc' })
      assert.strictEqual(r.ok, true, 'B: dispatch succeeds')
      assert.strictEqual(probeCmds(execLog).length, 2, 'B: pre + post probe still both run')
      assert.strictEqual(tripJournals(execLog).length, 0, 'B: a confined dispatch journals NO tripwire event')
      assert.ok(!logs.some((m) => m.includes('CONFINEMENT-BREACH')), 'B: no breach notice on a clean run')
      console.log('OK: #355 tripwire is silent when the engine stays confined')
    } finally { globalThis.__SR_ROOT = saved }
  }

  // -------------------------------------------------------------------
  // Case C: __SR_ROOT unset (most smokes / unrooted runs) -> the tripwire is a NO-OP: no probe execs at
  // all, byte-unchanged legacy behavior.
  // -------------------------------------------------------------------
  {
    const logs = []
    global.log = (m) => logs.push(m)
    const execLog = []
    global.agent = makeWriteStub(execLog, ['__SR_TRIP__ 5 abc 0\n', '__SR_TRIP__ 7 abc 0\n'])
    const saved = globalThis.__SR_ROOT
    delete globalThis.__SR_ROOT
    try {
      const r = await d.dispatchExternal({ engine: 'cursor', roleKind: 'fix', effort: 'high', prompt: 'fix',
        cwd: '/tmp/wt', schema: {}, timeoutSeconds: 300, taskId: 'T1', workItem: 'wi-abc' })
      assert.strictEqual(r.ok, true, 'C: dispatch succeeds')
      assert.strictEqual(probeCmds(execLog).length, 0, 'C: no primary-repo probe when __SR_ROOT is unset')
      assert.strictEqual(tripJournals(execLog).length, 0, 'C: no tripwire journal when unrooted')
      console.log('OK: #355 tripwire is a no-op when __SR_ROOT is unset (back-compat)')
    } finally { if (saved === undefined) delete globalThis.__SR_ROOT; else globalThis.__SR_ROOT = saved }
  }

  // -------------------------------------------------------------------
  // Case D: an uncommitted write to the PRIMARY tree (porcelain grows) with no reflog/HEAD move -> fires
  // on the primary-worktree-dirtied signal.
  // -------------------------------------------------------------------
  {
    const logs = []
    global.log = (m) => logs.push(m)
    const execLog = []
    global.agent = makeWriteStub(execLog, ['__SR_TRIP__ 5 abc 0\n', '__SR_TRIP__ 5 abc 3\n'])
    const saved = globalThis.__SR_ROOT
    globalThis.__SR_ROOT = '/primary'
    try {
      await d.dispatchExternal({ engine: 'cursor', roleKind: 'build', effort: 'high', prompt: 'build',
        cwd: '/tmp/wt', schema: {}, timeoutSeconds: 300, taskId: 'T1', workItem: 'wi-abc' })
      const tj = tripJournals(execLog)
      assert.strictEqual(tj.length, 1, 'D: dirtied primary tree fires the tripwire')
      const payload = JSON.parse(tj[0].match(/--payload '(.*)'$/s)[1])
      assert.ok(payload.confinementBreach.includes('primary-worktree-dirtied'),
        'D: the journal names the dirtied-tree signal: ' + JSON.stringify(payload.confinementBreach))
      console.log('OK: #355 tripwire fires on an uncommitted write to the primary tree')
    } finally { globalThis.__SR_ROOT = saved }
  }

  // -------------------------------------------------------------------
  // Case E: read roles are engine-read-only-sandboxed and author-plan's cwd IS the repo root (no
  // confinement boundary) — the tripwire is scoped to WRITE roles, so a review dispatch with __SR_ROOT
  // set fires NO probe.
  // -------------------------------------------------------------------
  {
    const logs = []
    global.log = (m) => logs.push(m)
    const execLog = []
    global.agent = async (prompt) => {
      execLog.push(prompt)
      if (prompt.includes('codex') && prompt.includes('perl -e')) return markedStdout('{}')
      if (prompt.includes('__SR_TRIP__')) return [{ index: 0, ok: true, stdout: '__SR_TRIP__ 5 abc 0\n' }]
      if (prompt.includes('engine_adapter.py build-argv')) return [{ index: 0, ok: true, stdout: JSON.stringify(['codex', 'exec', '--sandbox', 'read-only', '-']) }]
      if (prompt.includes('engine_adapter.py parse-result')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true, findings: [] }) }]
      if (prompt.includes('journal_entry.py')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
      return [{ index: 0, ok: true, stdout: '{}' }]
    }
    const saved = globalThis.__SR_ROOT
    globalThis.__SR_ROOT = '/primary'
    try {
      await d.dispatchExternal({ engine: 'codex', roleKind: 'review', effort: 'high', prompt: 'review',
        cwd: '/tmp/wt', schema: {}, timeoutSeconds: 300, workItem: 'wi-abc' })
      assert.strictEqual(probeCmds(execLog).length, 0, 'E: a read role fires no confinement probe (write-role scoped)')
      assert.strictEqual(tripJournals(execLog).length, 0, 'E: no tripwire journal for a read role')
      console.log('OK: #355 tripwire is scoped to write roles (read role fires no probe)')
    } finally { globalThis.__SR_ROOT = saved }
  }

  // -------------------------------------------------------------------
  // Case F: the pre-snapshot probe returns an UNPARSEABLE line (git error / courier drop) -> the tripwire
  // is INERT (it cannot assert an escape it never established a baseline for) — no post-probe, no journal,
  // no notice. Fail toward NOT crying wolf on a probe failure.
  // -------------------------------------------------------------------
  {
    const logs = []
    global.log = (m) => logs.push(m)
    const execLog = []
    global.agent = makeWriteStub(execLog, [null, '__SR_TRIP__ 7 abc 0\n'])
    const saved = globalThis.__SR_ROOT
    globalThis.__SR_ROOT = '/primary'
    try {
      const r = await d.dispatchExternal({ engine: 'cursor', roleKind: 'fix', effort: 'high', prompt: 'fix',
        cwd: '/tmp/wt', schema: {}, timeoutSeconds: 300, taskId: 'T1', workItem: 'wi-abc' })
      assert.strictEqual(r.ok, true, 'F: dispatch still succeeds')
      assert.strictEqual(probeCmds(execLog).length, 1, 'F: an unparseable pre-probe means NO post-probe (inert)')
      assert.strictEqual(tripJournals(execLog).length, 0, 'F: no tripwire journal when the baseline probe failed')
      assert.ok(!logs.some((m) => m.includes('CONFINEMENT-BREACH')), 'F: no breach notice on a failed baseline')
      console.log('OK: #355 tripwire is inert (no false alarm) when its baseline probe fails')
    } finally { globalThis.__SR_ROOT = saved }
  }

  // -------------------------------------------------------------------
  // Case G: __SR_ROOT set but EQUAL to cwd (the dispatch already runs at the primary — no confinement
  // boundary to police) -> no probe.
  // -------------------------------------------------------------------
  {
    const logs = []
    global.log = (m) => logs.push(m)
    const execLog = []
    global.agent = makeWriteStub(execLog, ['__SR_TRIP__ 5 abc 0\n', '__SR_TRIP__ 7 abc 0\n'])
    const saved = globalThis.__SR_ROOT
    globalThis.__SR_ROOT = '/tmp/wt'
    try {
      await d.dispatchExternal({ engine: 'cursor', roleKind: 'fix', effort: 'high', prompt: 'fix',
        cwd: '/tmp/wt', schema: {}, timeoutSeconds: 300, taskId: 'T1', workItem: 'wi-abc' })
      assert.strictEqual(probeCmds(execLog).length, 0, 'G: no probe when the dispatch cwd IS the primary root')
      console.log('OK: #355 tripwire skips when cwd equals the primary root')
    } finally { globalThis.__SR_ROOT = saved }
  }

  // -------------------------------------------------------------------
  // Case H: detection is ORTHOGONAL to the dispatch outcome. A dispatch that COMPLETED but FAILED its task
  // (parse-result ok:false) while its subprocess escaped to the primary must STILL journal the breach — the
  // highest-risk shape (an engine that fails yet committed to the primary on the way out). Guards a mutant
  // that hides the tripwire behind `if (parsed.ok)` or moves it after an early failure return.
  {
    const logs = []
    global.log = (m) => logs.push(m)
    const execLog = []
    let tripCall = 0
    global.agent = async (prompt) => {
      execLog.push(prompt)
      if ((prompt.includes('cursor-agent') || prompt.includes('--trust')) && prompt.includes('perl -e')) return markedStdout('{"raw":"out"}')
      if (prompt.includes('__SR_TRIP__')) { const st = ['__SR_TRIP__ 5 abc 0\n', '__SR_TRIP__ 7 abc 0\n'][tripCall]; tripCall += 1; return [{ index: 0, ok: true, stdout: st }] }
      if (prompt.includes('git') && prompt.includes('rev-parse HEAD')) return [{ index: 0, ok: true, stdout: 'preSHA-abc\n' }]
      if (prompt.includes('engine_adapter.py build-argv')) return [{ index: 0, ok: true, stdout: JSON.stringify(['cursor-agent', '--trust', '-f']) }]
      if (prompt.includes('engine_adapter.py parse-result')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: false, reason: 'plan_wrong' }) }]
      if (prompt.includes('journal_entry.py')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
      return [{ index: 0, ok: true, stdout: '{}' }]
    }
    const saved = globalThis.__SR_ROOT
    globalThis.__SR_ROOT = '/primary'
    try {
      const r = await d.dispatchExternal({ engine: 'cursor', roleKind: 'fix', effort: 'high', prompt: 'fix',
        cwd: '/tmp/wt', schema: {}, timeoutSeconds: 300, taskId: 'T1', workItem: 'wi-abc' })
      assert.strictEqual(r.ok, false, 'H: the dispatch itself FAILED (parse ok:false)')
      const tj = tripJournals(execLog)
      assert.strictEqual(tj.length, 1, 'H: a FAILED-but-completed dispatch still journals the breach (orthogonal to outcome)')
      const payload = JSON.parse(tj[0].match(/--payload '(.*)'$/s)[1])
      assert.strictEqual(payload.outcome, 'confinement-breach', 'H: outcome is a breach')
      assert.ok(payload.confinementBreach.includes('primary-HEAD-reflog-grew'), 'H: names the reflog signal')
      console.log('OK: #355 tripwire fires on a FAILED-but-completed dispatch (orthogonal to outcome)')
    } finally { globalThis.__SR_ROOT = saved }
  }

  // -------------------------------------------------------------------
  // Case I: a TIMEOUT (the JS race abandoned an un-joined, possibly-still-writing CLI) with a clean
  // post-probe must NOT be reported as confined — it is INDETERMINATE (premortem-001). A silent "clean" on
  // the runaway path most likely to be escaping is false comfort.
  // -------------------------------------------------------------------
  {
    const logs = []
    global.log = (m) => logs.push(m)
    const execLog = []
    let tripCall = 0
    global.agent = async (prompt) => {
      execLog.push(prompt)
      if (prompt.includes('__SR_TRIP__')) { tripCall += 1; return [{ index: 0, ok: true, stdout: '__SR_TRIP__ 5 abc 0\n' }] }
      if (prompt.includes('git') && prompt.includes('rev-parse HEAD')) return [{ index: 0, ok: true, stdout: 'preSHA-abc\n' }]
      if (prompt.includes('engine_adapter.py build-argv')) return [{ index: 0, ok: true, stdout: JSON.stringify(['cursor-agent', '--trust', '-f']) }]
      if (prompt.includes('journal_entry.py')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
      if ((prompt.includes('cursor-agent') || prompt.includes('--trust')) && prompt.includes('perl -e')) return new Promise(() => {})   // CLI wedges -> race times out, run never joins
      return [{ index: 0, ok: true, stdout: '{}' }]
    }
    const saved = globalThis.__SR_ROOT
    globalThis.__SR_ROOT = '/primary'
    try {
      const r = await d.dispatchExternal({ engine: 'cursor', roleKind: 'fix', effort: 'high', prompt: 'fix',
        cwd: '/tmp/wt', schema: {}, timeoutSeconds: 0.05, taskId: 'T1', workItem: 'wi-abc' })
      assert.strictEqual(r.reason, 'timeout', 'I: the dispatch was ceiling-killed (timeout)')
      const tj = tripJournals(execLog)
      assert.strictEqual(tj.length, 1, 'I: a timed-out dispatch journals an INDETERMINATE tripwire line')
      const payload = JSON.parse(tj[0].match(/--payload '(.*)'$/s)[1])
      assert.strictEqual(payload.outcome, 'confinement-indeterminate', 'I: a clean post-probe on an un-joined CLI is INDETERMINATE, not confined')
      assert.strictEqual(payload.dispatchReason, 'timeout', 'I: the journal names the un-joined reason')
      assert.ok(logs.some((m) => m.includes('CONFINEMENT-INDETERMINATE')), 'I: a distinct INDETERMINATE narrator notice fired')
      assert.ok(!logs.some((m) => m.includes('CONFINEMENT-BREACH')), 'I: never falsely claims a clean breach on an un-joined CLI')
      console.log('OK: #355 timeout with a clean post-probe reports INDETERMINATE, not confined')
    } finally { globalThis.__SR_ROOT = saved }
  }

  // -------------------------------------------------------------------
  // Case J: pin the pure classifier + probe composer directly via the test-only exports (the HEAD-moved
  // branch is otherwise unexercised by the dispatch cases, which hold head constant).
  // -------------------------------------------------------------------
  {
    assert.deepStrictEqual(d._confinementBreach({ reflog: 5, head: 'aaa', status: 0 }, { reflog: 5, head: 'bbb', status: 0 }),
      ['primary-HEAD-moved'], 'J: a moved primary HEAD (same reflog count + clean tree) is a breach')
    assert.deepStrictEqual(d._confinementBreach({ reflog: 5, head: 'a', status: 1 }, { reflog: 8, head: 'b', status: 3 }),
      ['primary-HEAD-reflog-grew', 'primary-HEAD-moved', 'primary-worktree-dirtied'], 'J: all three signals compose in order')
    assert.strictEqual(d._confinementBreach({ reflog: 5, head: 'a', status: 0 }, { reflog: 5, head: 'a', status: 0 }), null,
      'J: an unchanged primary repo is not a breach')
    assert.strictEqual(d._confinementBreach(null, { reflog: 5, head: 'a', status: 0 }), null, 'J: a null baseline is inert')
    assert.strictEqual(d._confinementBreach({ reflog: 5, head: 'a', status: 0 }, null), null, 'J: a null post is inert')
    // reflog is append-only: a (pathological) count DECREASE is not treated as growth.
    assert.strictEqual(d._confinementBreach({ reflog: 7, head: 'a', status: 0 }, { reflog: 5, head: 'a', status: 0 }), null,
      'J: a reflog count decrease alone is not a growth breach')
    const probe = d._confinementProbeCmd('/primary')
    assert.ok(probe.includes("git -C '/primary' reflog show HEAD") && probe.includes("git -C '/primary' status --porcelain") &&
      probe.includes("git -C '/primary' rev-parse HEAD") && probe.includes('__SR_TRIP__'),
      'J: the probe composes the sentinel + all three git reads against the given root')
    console.log('OK: #355 classifier + probe composer pinned directly (HEAD-moved branch, order, null-safety)')
  }

  console.log('ALL OK: #355 engine confinement tripwire')
})().catch((e) => { console.error(e && e.stack || e); process.exit(1) })
