// plugins/superheroes/lib/tests/showrunner_journal_idem_smoke.js
// #350 Part A (journal truth under courier retries): engine_dispatch._journalExternal bakes a per-call
// idempotence nonce (--idem) into the external_dispatch append command. _execJson re-runs the IDENTICAL
// command on a courier stdout-drop, so both attempts carry the SAME --idem — journal.append then dedupes
// and the 2026-07-10 doubled-line signature cannot recur. Two DISTINCT dispatches carry DIFFERENT nonces
// (a content-derived key would wrongly collapse two identical-payload failures — the #378 case). And a
// NON-DENIAL staging failure now carries the failed leaf's error/exit as the journal `reason` (the
// 2026-07-12 empty-reason blind spot).
const assert = require('assert')
const { markedStdout } = require('./_marked_stdout.js')
const logs = []
global.log = (m) => logs.push(m)

// Route an exec() command by substring; per-call hooks let a test drop stdout on the FIRST journal leaf.
function makeExec(onJournal) {
  let journalCalls = 0
  const execLog = []
  global.agent = async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    if (label !== 'exec') return ''
    execLog.push(prompt)
    if (prompt.includes('journal_entry.py')) {
      journalCalls += 1
      return onJournal ? onJournal(journalCalls) : [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
    }
    if (prompt.includes('engine_adapter.py build-argv')) {
      return [{ index: 0, ok: true, stdout: JSON.stringify(['codex', 'exec', '--sandbox', 'read-only', '-']) }]
    }
    if (prompt.includes('engine_adapter.py parse-result')) {
      return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true, findings: [] }) }]
    }
    if (prompt.includes('--sandbox')) return markedStdout('{"raw":"external review output"}')
    return [{ index: 0, ok: true, stdout: '{}' }]
  }
  return execLog
}

function idemOf(cmd) { const m = cmd.match(/--idem '([^']+)'/); return m && m[1] }

;(async () => {
  const d = require('../engine_dispatch.js')

  // -------------------------------------------------------------------------------------------------
  // (1) The idem nonce is STABLE across the _execJson journal retry: a first-attempt stdout-drop makes
  //     _execJson re-run the identical command; BOTH attempts must carry the SAME --idem so the real
  //     journal.append dedupes to ONE line (the doubled-line fix).
  // -------------------------------------------------------------------------------------------------
  {
    const execLog = makeExec((n) => n === 1
      ? [{ index: 0, ok: true, stdout: '' }]                              // courier drop -> _execJson retries
      : [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }])
    await d.dispatchExternal({ workItem: 'wi-idem', engine: 'codex', roleKind: 'review', effort: 'high',
      prompt: 'review', cwd: '/tmp/wt', schema: {}, timeoutSeconds: 300 })
    const idems = execLog.filter((c) => c.includes('journal_entry.py') && c.includes('external_dispatch')).map(idemOf)
    assert.ok(idems.every(Boolean), 'every external_dispatch journal command must carry an --idem nonce')
    // The dropped-then-retried logical journal produced TWO commands with the SAME idem — the exact
    // sequence journal.append dedupes to one line. No other idem repeats (distinct logical journals get
    // distinct nonces), so exactly one idem value appears twice.
    const counts = {}
    for (const id of idems) counts[id] = (counts[id] || 0) + 1
    const doubled = Object.keys(counts).filter((id) => counts[id] > 1)
    assert.strictEqual(doubled.length, 1, 'exactly the retried journal re-sends its nonce (one idem repeats)')
    assert.strictEqual(counts[doubled[0]], 2, 'the retry re-sends the SAME --idem exactly once (append then dedupes)')
    console.log('OK: #350 the journal retry re-sends the identical --idem nonce (append dedupes -> no doubled line)')
  }

  // -------------------------------------------------------------------------------------------------
  // (2) DISTINCT dispatches carry DISTINCT nonces (per-call counter, never content-derived) — so two
  //     genuinely-separate journal appends with byte-identical payloads still each write (#378 guard).
  // -------------------------------------------------------------------------------------------------
  {
    const execLog = makeExec(null)
    const base = { workItem: 'wi-idem', engine: 'codex', roleKind: 'review', effort: 'high',
      prompt: 'review', cwd: '/tmp/wt', schema: {}, timeoutSeconds: 300 }
    await d.dispatchExternal(base)
    await d.dispatchExternal(base)
    const idems = execLog.filter((c) => c.includes('journal_entry.py') && c.includes('external_dispatch')).map(idemOf)
    assert.ok(idems.length >= 2, 'two dispatches journal at least two external_dispatch lines')
    assert.strictEqual(new Set(idems).size, idems.length, 'each distinct dispatch gets a distinct idem nonce')
    console.log('OK: #350 distinct dispatches get distinct idem nonces (identical-payload failures never collapse)')
  }

  // -------------------------------------------------------------------------------------------------
  // (3) A NON-DENIAL staging failure carries the failed leaf's error/exit as the journal reason — the
  //     2026-07-12 empty-reason blind spot. The staging leaf (hashlib.sha256) fails persistently with an
  //     exit code + error prose and NO denial signature.
  // -------------------------------------------------------------------------------------------------
  {
    const execLog = []
    global.agent = async (prompt, opts) => {
      const label = (opts && opts.label) || ''
      if (label !== 'exec') return ''
      execLog.push(prompt)
      if (prompt.includes(d._SR_STAGE_SIG)) return [{ index: 0, ok: false, status: 1, error: 'ENOSPC: no space left on device', stdout: '' }]
      if (prompt.includes('journal_entry.py')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
      // scrub seam (pr_comment.py scrub) — echo the reason back unchanged (no secrets to redact)
      if (prompt.includes('pr_comment.py scrub')) {
        const m = prompt.match(/printf '%s' '([\s\S]*?)' \| python3/)
        return [{ index: 0, ok: true, stdout: m ? m[1].replace(/'\\''/g, "'") : '' }]
      }
      return [{ index: 0, ok: true, stdout: '{}' }]
    }
    const r = await d.dispatchExternal({ workItem: 'wi-stage', engine: 'codex', roleKind: 'review', effort: 'high',
      prompt: 'review', cwd: '/tmp/wt', schema: {}, timeoutSeconds: 300 })
    assert.strictEqual(r.reason, 'could-not-stage-external-inputs', 'a persistent staging failure returns the harness-dead reason')
    const stagingJournal = execLog.find((c) => c.includes('journal_entry.py') && c.includes('staging-failed'))
    assert.ok(stagingJournal, 'a non-denial staging failure journals a staging-failed external_dispatch line')
    const payloadMatch = stagingJournal.match(/--payload '([\s\S]*)'/)
    const payload = JSON.parse(payloadMatch[1].replace(/'\\''/g, "'"))
    assert.ok(payload.reason && /exit 1/.test(payload.reason),
      'staging-failed must carry the failed leaf exit code: ' + JSON.stringify(payload.reason))
    assert.ok(/no space left/i.test(payload.reason),
      'staging-failed must carry the failed leaf error prose: ' + JSON.stringify(payload.reason))
    console.log('OK: #350 a non-denial staging-failed line carries the failed leaf error/exit (no more empty reason)')
  }

  console.log('ALL OK: showrunner_journal_idem_smoke')
})().catch((e) => { console.error(e); process.exit(1) })
