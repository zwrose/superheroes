// plugins/superheroes/lib/tests/showrunner_journal_idem_smoke.js
// #350 Part A (journal truth under courier retries): engine_dispatch._journalExternal bakes a per-call,
// RESUME-SAFE idempotence nonce (--idem) into the external_dispatch append command. The nonce is a counter
// SEEDED from the journal's max `${wi}:d<N>` ordinal (--max-idem-prefix query), so:
//   (1) _execJson re-runs the IDENTICAL command on a courier stdout-drop -> both attempts carry the SAME
//       --idem -> journal.append dedupes -> the 2026-07-10 doubled-line signature cannot recur;
//   (1b) a RESUMED run continues the sequence past the pre-crash tail (never re-mints a colliding d1..dN);
//   (2) two DISTINCT dispatches carry DIFFERENT nonces (a content-derived key would wrongly collapse two
//       identical-payload failures — the #378 case).
// And a NON-DENIAL staging failure carries the failed leaf's OUTPUT as the journal `reason` (the
// 2026-07-12 empty-reason blind spot) — the dumb-pipe exec shape is {index, ok, stdout}, no exit code.
const assert = require('assert')
const { markedStdout } = require('./_marked_stdout.js')
const logs = []
global.log = (m) => logs.push(m)

// Route an exec() command by substring. `seedMax` answers the --max-idem-prefix seed query; `onAppend`
// (per external_dispatch append call) lets a test drop stdout on the first append to force an _execJson retry.
function makeExec(seedMax, onAppend) {
  let appendCalls = 0
  const execLog = []
  global.agent = async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    if (label !== 'exec') return ''
    execLog.push(prompt)
    if (prompt.includes('--max-idem-prefix')) {
      return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true, max: seedMax == null ? 0 : seedMax }) }]
    }
    if (prompt.includes('journal_entry.py') && prompt.includes('external_dispatch')) {
      appendCalls += 1
      return onAppend ? onAppend(appendCalls) : [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
    }
    if (prompt.includes('journal_entry.py')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
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

function appendIdems(execLog) {
  return execLog.filter((c) => c.includes('journal_entry.py') && c.includes('external_dispatch'))
    .map((c) => { const m = c.match(/--idem '([^']+)'/); return m && m[1] })
}

;(async () => {
  const d = require('../engine_dispatch.js')
  const review = (workItem) => ({ workItem, engine: 'codex', roleKind: 'review', effort: 'high',
    prompt: 'review', cwd: '/tmp/wt', schema: {}, timeoutSeconds: 300 })

  // (1) idem STABLE across the _execJson journal retry: a first-attempt stdout-drop re-runs the identical
  //     command; the dropped-then-retried logical append shows up as ONE idem value appearing twice — the
  //     exact sequence journal.append dedupes to a single line.
  {
    const execLog = makeExec(0, (n) => n === 1
      ? [{ index: 0, ok: true, stdout: '' }]                              // courier drop -> _execJson retries
      : [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }])
    await d.dispatchExternal(review('wi-idem-1'))
    const idems = appendIdems(execLog)
    assert.ok(idems.length >= 1 && idems.every(Boolean), 'every external_dispatch append carries an --idem nonce')
    const counts = {}
    for (const id of idems) counts[id] = (counts[id] || 0) + 1
    const doubled = Object.keys(counts).filter((id) => counts[id] > 1)
    assert.strictEqual(doubled.length, 1, 'exactly the retried append re-sends its nonce (one idem repeats)')
    assert.strictEqual(counts[doubled[0]], 2, 'the retry re-sends the SAME --idem exactly once (append then dedupes)')
    console.log('OK: #350 the journal retry re-sends the identical --idem nonce (append dedupes -> no doubled line)')
  }

  // (1b) RESUME-SAFE: the nonce is SEEDED from the journal's max ordinal, so a resumed run whose journal
  //      already holds wi:d1..d5 mints wi:d6 next — never a colliding d1 that would be silently deduped.
  {
    const execLog = makeExec(5, null)
    await d.dispatchExternal(review('wi-resume'))
    const idems = appendIdems(execLog).filter(Boolean)
    assert.ok(idems.length >= 1, 'the resumed dispatch journals at least one external_dispatch line')
    const ordinals = idems.map((id) => Number(id.split(':d')[1]))
    assert.ok(ordinals.every((o) => o > 5), 'every post-resume nonce continues PAST the pre-crash tail (d>5): ' + JSON.stringify(idems))
    assert.ok(execLog.some((c) => c.includes('--max-idem-prefix')), 'the seed read (--max-idem-prefix) is issued to continue the sequence')
    console.log('OK: #350 the nonce is seeded from the journal (a resumed run never re-mints a colliding pre-crash nonce)')
  }

  // (2) DISTINCT dispatches carry DISTINCT nonces (a seeded counter, never content-derived) — so two
  //     genuinely-separate journal appends with byte-identical payloads still each write (#378 guard).
  {
    const execLog = makeExec(0, null)
    await d.dispatchExternal(review('wi-distinct'))
    await d.dispatchExternal(review('wi-distinct'))
    const idems = appendIdems(execLog).filter(Boolean)
    assert.ok(idems.length >= 2, 'two dispatches journal at least two external_dispatch lines')
    assert.strictEqual(new Set(idems).size, idems.length, 'each distinct dispatch gets a distinct idem nonce')
    console.log('OK: #350 distinct dispatches get distinct idem nonces (identical-payload failures never collapse)')
  }

  // (3) A NON-DENIAL staging failure carries the failed leaf's OUTPUT as the journal reason — the
  //     2026-07-12 empty-reason blind spot. The staging leaf (hashlib.sha256) fails persistently with
  //     error text in stdout (the real dumb-pipe exec shape {index, ok, stdout}) and NO denial signature.
  {
    const execLog = []
    global.agent = async (prompt, opts) => {
      const label = (opts && opts.label) || ''
      if (label !== 'exec') return ''
      execLog.push(prompt)
      if (prompt.includes('--max-idem-prefix')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true, max: 0 }) }]
      if (prompt.includes(d._SR_STAGE_SIG)) return [{ index: 0, ok: false, stdout: 'ENOSPC: no space left on device' }]
      if (prompt.includes('journal_entry.py')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
      if (prompt.includes('pr_comment.py scrub')) {                       // scrub seam: echo unchanged (no secret)
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
    const payload = JSON.parse(stagingJournal.match(/--payload '([\s\S]*)'/)[1].replace(/'\\''/g, "'"))
    assert.ok(payload.reason && /no space left/i.test(payload.reason),
      'staging-failed must carry the failed leaf output (no more empty reason): ' + JSON.stringify(payload.reason))
    console.log('OK: #350 a non-denial staging-failed line carries the failed leaf output (no more empty reason)')
  }

  console.log('ALL OK: showrunner_journal_idem_smoke')
})().catch((e) => { console.error(e); process.exit(1) })
