// plugins/superheroes/lib/tests/showrunner_exec_persist_smoke.js
// TDD smoke: proves exec() dumb-pipe + persistPhase() seam (Task 10).
//
// Assertions:
//   (a) exec(['cmd1','cmd2']) issues ONE agent call whose prompt contains both commands
//       and whose opts.model is 'haiku' REGARDLESS of any __SR_LEAF_MODEL override.
//   (b) persistPhase composes journal_entry BEFORE checkpoint_entry (asserted by index
//       in the batched prompt) and returns {ok:true} on success, {ok:false} on failure.
//   (c) every interpolated arg is shq()-quoted: single-quoted payloads appear in the prompt,
//       no raw unquoted JSON blobs.
'use strict'
const assert = require('assert')

// Require only what we need; the file exports exec and persistPhase.
const sr = require('../showrunner.js')

function saveProgressOk(extra) {
  return [{ ok: true, stdout: JSON.stringify(Object.assign({ ok: true, journal_confirmed: true, checkpoint_confirmed: true }, extra || {})) }]
}

;(async () => {
  // ---- Stub globalThis.agent to record calls ----
  const calls = []
  globalThis.agent = async (prompt, opts) => {
    calls.push({ prompt, opts: opts || {} })
    // Return a canned successful result array (one entry per command).
    return [{ index: 0, ok: true, stdout: 'ok-0' }, { index: 1, ok: true, stdout: 'ok-1' }]
  }
  // Also need globalThis.__SR_LEAF_MODEL set to something non-haiku to prove override.
  globalThis.__SR_LEAF_MODEL = 'opus'

  // ---- (a) exec issues ONE call with both commands; model forced to 'haiku' ----
  const results = await sr.exec(['echo cmd1', 'echo cmd2'])
  assert.strictEqual(calls.length, 1, 'exec dispatches exactly one agent call')
  const { prompt: ep, opts: eo } = calls[0]
  assert.ok(ep.includes('echo cmd1'), 'exec prompt contains cmd1')
  assert.ok(ep.includes('echo cmd2'), 'exec prompt contains cmd2')
  assert.strictEqual(eo.model, 'haiku', 'exec forces model to haiku (cheapestModel) regardless of __SR_LEAF_MODEL')
  assert.ok(Array.isArray(results), 'exec returns an array')
  assert.strictEqual(results.length, 2, 'exec returns one result per command')
  assert.strictEqual(results[0].ok, true, 'result[0].ok is true')
  assert.strictEqual(results[0].index, 0, 'result[0].index is 0')

  // ---- (b) persistPhase: folded save phase progress courier; {ok:true} on success ----
  calls.length = 0
  globalThis.agent = async (prompt, opts) => {
    calls.push({ prompt, opts: opts || {} })
    if ((opts && opts.label) === 'save phase progress') {
      return saveProgressOk()
    }
    return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }, { index: 1, ok: true, stdout: JSON.stringify({ ok: true }) }]
  }

  const payload = { phase: 'plan', gate: 'passed', confidence: 'high', assumptions: [] }
  const ok = await sr.persistPhase('wi-test', {
    sideEffectCmd: 'echo side-effect',
    journalPayload: payload,
    step: 3,
    phase: 'review-plan',
  })
  assert.strictEqual(calls.length, 1, 'persistPhase dispatches exactly one save phase progress courier call')
  const pp = calls[0].prompt
  const progressIdx = pp.indexOf('phase_progress_entry.py')
  assert.ok(progressIdx >= 0, 'prompt contains phase_progress_entry.py save')
  const sideIdx = pp.indexOf('echo side-effect')
  assert.ok(sideIdx >= 0, 'prompt contains the sideEffectCmd')
  assert.ok(sideIdx < progressIdx, 'sideEffectCmd appears before the save command')
  assert.deepStrictEqual(ok, { ok: true, recovered: false }, 'persistPhase returns {ok:true, recovered:false} when read-back succeeds')

  // ---- (b) persistPhase: {ok:false} when read-back fails ----
  calls.length = 0
  globalThis.agent = async (prompt, opts) => {
    calls.push({ prompt, opts: opts || {} })
    if ((opts && opts.label) === 'save phase progress') {
      return saveProgressOk({ ok: false, journal_confirmed: false, checkpoint_confirmed: false })
    }
    return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
  }
  const fail = await sr.persistPhase('wi-test', {
    journalPayload: { phase: 'plan' },
    step: 2,
    phase: 'plan',
  })
  assert.ok(fail && fail.ok === false, 'persistPhase returns {ok:false} when read-back fails')

  // ---- (b-retry) persistPhase courier-drop retry on save phase progress ----
  calls.length = 0
  let batchCall = 0
  globalThis.agent = async (prompt, opts) => {
    calls.push({ prompt, opts: opts || {} })
    if ((opts && opts.label) !== 'save phase progress') return saveProgressOk()
    batchCall += 1
    return batchCall === 1 ? [{ ok: true, stdout: '' }] : saveProgressOk()
  }
  const dropRecovered = await sr.persistPhase('wi-drop', { journalPayload: { phase: 'plan' }, step: 1, phase: 'plan' })
  assert.deepStrictEqual(dropRecovered, { ok: true, recovered: false }, 'persistPhase retries once on a dropped stdout and returns {ok:true}')
  assert.strictEqual(batchCall, 2, 'persistPhase retries exactly once on a courier-drop (2 save calls)')

  calls.length = 0
  let batchCall2 = 0
  globalThis.agent = async (prompt, opts) => {
    calls.push({ prompt, opts: opts || {} })
    if ((opts && opts.label) !== 'save phase progress') return saveProgressOk()
    batchCall2 += 1
    return [{ ok: true, stdout: '' }]
  }
  const dropPersists = await sr.persistPhase('wi-drop2', { journalPayload: { phase: 'plan' }, step: 1, phase: 'plan' })
  assert.ok(dropPersists && dropPersists.ok === false, 'persistPhase fails closed when stdout is dropped on BOTH attempts')
  assert.strictEqual(batchCall2, 2, 'persistPhase retries exactly once before failing closed (2 save calls)')

  calls.length = 0
  let batchCall3 = 0
  globalThis.agent = async (prompt, opts) => {
    calls.push({ prompt, opts: opts || {} })
    if ((opts && opts.label) !== 'save phase progress') return saveProgressOk()
    batchCall3 += 1
    return saveProgressOk({ ok: false, journal_confirmed: false, checkpoint_confirmed: false })
  }
  const realFail = await sr.persistPhase('wi-realfail', { journalPayload: { phase: 'plan' }, step: 1, phase: 'plan' })
  assert.ok(realFail && realFail.ok === false, 'a genuine read-back failure returns {ok:false}')
  assert.strictEqual(batchCall3, 1, 'a genuine failure is NOT retried (1 save call)')

  calls.length = 0
  let batchCall4 = 0
  globalThis.agent = async (prompt, opts) => {
    calls.push({ prompt, opts: opts || {} })
    if ((opts && opts.label) === 'save phase progress') {
      batchCall4 += 1
      return saveProgressOk()
    }
    return saveProgressOk()
  }
  const setGateOk = await sr.persistPhase('wi-setgate', {
    sideEffectCmd: 'echo set-gate', journalPayload: { phase: 'plan' }, step: 1, phase: 'plan',
  })
  assert.deepStrictEqual(setGateOk, { ok: true, recovered: false }, 'side-effect + save succeeds in one courier call')
  assert.strictEqual(batchCall4, 1, 'a clean read-back on the first call returns immediately — one save call')

  calls.length = 0
  let batchCall5 = 0
  globalThis.agent = async (prompt, opts) => {
    calls.push({ prompt, opts: opts || {} })
    if ((opts && opts.label) === 'save phase progress') {
      batchCall5 += 1
      return [{ ok: false, stdout: 'transport failed' }]
    }
    return saveProgressOk()
  }
  const execFail = await sr.persistPhase('wi-execfail', {
    sideEffectCmd: 'echo set-gate', journalPayload: { phase: 'plan' }, step: 1, phase: 'plan',
  })
  assert.ok(execFail && execFail.ok === false, 'a transport failure returns {ok:false}')
  assert.strictEqual(batchCall5, 2, 'command failure retries once before failing closed (2 save calls)')

  // ---- (c) shq-quoting: no raw unquoted JSON in the prompt ----
  calls.length = 0
  const jsonPayload = { phase: 'review-plan', gate: 'passed', confidence: 'high', assumptions: ['x'] }
  globalThis.agent = async (prompt, opts) => {
    calls.push({ prompt, opts: opts || {} })
    if ((opts && opts.label) === 'save phase progress') return saveProgressOk()
    return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
  }
  await sr.persistPhase('wi-q', {
    journalPayload: jsonPayload,
    step: 5,
    phase: 'review-plan',
  })
  assert.strictEqual(calls.length, 1, 'persistPhase (no sideEffect) makes exactly one save call')
  const qp = calls[0].prompt
  assert.ok(!qp.includes("--payload {"), 'phase_progress_entry --payload is shq-quoted (no raw {')
  assert.ok(qp.includes("--payload '"), "phase_progress_entry --payload arg is single-quoted by shq")
  // Likewise --step and --phase must be single-quoted.
  assert.ok(qp.includes("--step '"), '--step arg is shq-quoted')
  assert.ok(qp.includes("--phase '"), '--phase arg is shq-quoted')

  // ---- (d) exec parses fenced/string leaf output (regression guard for live failure) ----
  // The live Workflow agent returns its text response as a STRING, often with markdown code fences.
  // Before the fix: Array.isArray(out) is false -> exec returns [] -> callers fail silently.
  // After the fix: exec strips the fence and JSON.parses the inner text.

  // (d1) markdown-fenced string with ```json tag (the exact live-failure case)
  calls.length = 0
  globalThis.agent = async (prompt, opts) => {
    calls.push({ prompt, opts: opts || {} })
    return '```json\n[{"index":0,"ok":true,"stdout":"OK"}]\n```'
  }
  const fencedResult = await sr.exec(['echo hello'])
  assert.ok(Array.isArray(fencedResult), 'exec returns array when leaf returns fenced ```json string')
  assert.strictEqual(fencedResult.length, 1, 'fenced result has one entry')
  assert.strictEqual(fencedResult[0].index, 0, 'fenced result[0].index is 0')
  assert.strictEqual(fencedResult[0].ok, true, 'fenced result[0].ok is true')
  assert.strictEqual(fencedResult[0].stdout, 'OK', 'fenced result[0].stdout is "OK"')

  // (d2) bare fence without language tag
  calls.length = 0
  globalThis.agent = async (prompt, opts) => {
    calls.push({ prompt, opts: opts || {} })
    return '```\n[{"index":0,"ok":true,"stdout":"bare"}]\n```'
  }
  const bareFenced = await sr.exec(['echo bare'])
  assert.ok(Array.isArray(bareFenced), 'exec returns array when leaf returns bare-fenced string')
  assert.strictEqual(bareFenced[0].stdout, 'bare', 'bare-fenced result stdout is "bare"')

  // (d3) clean JSON string with no fence
  calls.length = 0
  globalThis.agent = async (prompt, opts) => {
    calls.push({ prompt, opts: opts || {} })
    return '[{"index":0,"ok":true,"stdout":"clean"}]'
  }
  const cleanStr = await sr.exec(['echo clean'])
  assert.ok(Array.isArray(cleanStr), 'exec returns array when leaf returns clean JSON string')
  assert.strictEqual(cleanStr[0].stdout, 'clean', 'clean JSON string result stdout is "clean"')

  // (d4) existing array-returning stub path still works (no regression)
  calls.length = 0
  globalThis.agent = async (prompt, opts) => {
    calls.push({ prompt, opts: opts || {} })
    return [{ index: 0, ok: true, stdout: 'array-path' }]
  }
  const arrayPath = await sr.exec(['echo array'])
  assert.ok(Array.isArray(arrayPath), 'exec returns array when leaf returns array directly')
  assert.strictEqual(arrayPath[0].stdout, 'array-path', 'direct-array path stdout preserved')

  // (d5) genuinely unparseable string -> synthetic per-command failure array (fail-closed)
  calls.length = 0
  globalThis.agent = async (prompt, opts) => {
    calls.push({ prompt, opts: opts || {} })
    return 'not json at all'
  }
  const unparseable = await sr.exec(['cmd1', 'cmd2', 'cmd3'])
  assert.ok(Array.isArray(unparseable), 'exec returns array even on unparseable response')
  assert.strictEqual(unparseable.length, 3, 'synthetic failure array length === commands.length')
  assert.ok(unparseable.every(function(r) { return r.ok === false }), 'all synthetic failures have ok:false')
  assert.ok(unparseable[0].stdout.length > 0, 'synthetic failure has a non-empty stdout signal')

  // (d5b) persistPhase over a synthetic-failure result returns {ok:false} (no phantom {ok:true})
  calls.length = 0
  globalThis.agent = async (prompt, opts) => {
    calls.push({ prompt, opts: opts || {} })
    if ((opts && opts.label) === 'save phase progress') return 'not json at all'
    return saveProgressOk()
  }
  const phantomCheck = await sr.persistPhase('wi-phantom', {
    journalPayload: { phase: 'plan' },
    step: 1,
    phase: 'plan',
  })
  assert.ok(phantomCheck && phantomCheck.ok === false, 'persistPhase returns {ok:false} on unparseable courier output (no phantom ok:true)')

  // ---- (d6) prose BEFORE fence (the live failure shape) ----
  // Haiku prefixed the JSON with prose: "Perfect. Here's the result as a JSON array:\n\n```json\n[...]\n```"
  // The anchored ^```...```$ regex fails to match, so the current parser yields synthetic failure.
  // After the fix the parser should extract the fenced block from anywhere in the string.
  calls.length = 0
  globalThis.agent = async (prompt, opts) => {
    calls.push({ prompt, opts: opts || {} })
    return "Perfect. Here's the result as a JSON array:\n\n```json\n[{\"index\":0,\"ok\":true,\"stdout\":\"prose-ok\"}]\n```"
  }
  const proseFenced = await sr.exec(['echo prose'])
  assert.ok(Array.isArray(proseFenced), 'exec returns array when leaf prefixes fence with prose')
  assert.strictEqual(proseFenced.length, 1, 'prose-fenced result has one entry')
  assert.strictEqual(proseFenced[0].index, 0, 'prose-fenced result[0].index is 0')
  assert.strictEqual(proseFenced[0].ok, true, 'prose-fenced result[0].ok is true')
  assert.strictEqual(proseFenced[0].stdout, 'prose-ok', 'prose-fenced result[0].stdout is "prose-ok"')

  // ---- (d7) prose AROUND bare JSON (no fence) ----
  // e.g. "Here it is: [{...}]\nAll done."
  calls.length = 0
  globalThis.agent = async (prompt, opts) => {
    calls.push({ prompt, opts: opts || {} })
    return 'Here it is: [{"index":0,"ok":true,"stdout":"bare-prose"}]\nAll done.'
  }
  const bareProse = await sr.exec(['echo bare-prose'])
  assert.ok(Array.isArray(bareProse), 'exec returns array when leaf surrounds bare JSON with prose')
  assert.strictEqual(bareProse.length, 1, 'prose-around-JSON result has one entry')
  assert.strictEqual(bareProse[0].ok, true, 'prose-around-JSON result[0].ok is true')
  assert.strictEqual(bareProse[0].stdout, 'bare-prose', 'prose-around-JSON result[0].stdout is "bare-prose"')

  // ---- (e) FR-5 cd-prefix: selfContained() and exec() with __SR_ROOT set ----
  // (e1) exec with __SR_ROOT set: every command gets `cd '<root>' && ` prefix in the prompt.
  const savedRoot = globalThis.__SR_ROOT
  try {
    globalThis.__SR_ROOT = '/some/root'
    calls.length = 0
    globalThis.agent = async (prompt, opts) => {
      calls.push({ prompt, opts: opts || {} })
      return [{ index: 0, ok: true, stdout: 'cd-ok' }]
    }
    await sr.exec(['python3 foo.py'])
    assert.ok(calls[0].prompt.includes("cd '/some/root' && python3 foo.py"),
      'exec cd-prefixes commands when __SR_ROOT is set')

    // (e2) exec with __SR_ROOT unset: no cd prefix (backward compat).
    globalThis.__SR_ROOT = undefined
    calls.length = 0
    globalThis.agent = async (prompt, opts) => {
      calls.push({ prompt, opts: opts || {} })
      return [{ index: 0, ok: true, stdout: 'no-cd-ok' }]
    }
    await sr.exec(['python3 bar.py'])
    assert.ok(!calls[0].prompt.includes('cd '), 'exec does NOT cd-prefix when __SR_ROOT is unset')

    // (e3) command already starting with `cd ` is NOT double-prefixed.
    globalThis.__SR_ROOT = '/some/root'
    calls.length = 0
    globalThis.agent = async (prompt, opts) => {
      calls.push({ prompt, opts: opts || {} })
      return [{ index: 0, ok: true, stdout: 'already-cd-ok' }]
    }
    await sr.exec(['cd /build-worktree && python3 foo.py'])
    const alreadyCdPrompt = calls[0].prompt
    // Must contain the original command unchanged (not double-cd'd).
    assert.ok(alreadyCdPrompt.includes('cd /build-worktree && python3 foo.py'),
      'exec preserves command already starting with cd (no double-prefix)')
    assert.ok(!alreadyCdPrompt.includes("cd '/some/root' && cd /build-worktree"),
      'exec does NOT double-prefix a command that already starts with cd')

    // (e4) selfContained() helper exported and reusable.
    globalThis.__SR_ROOT = '/repo-root'
    assert.ok(sr.selfContained('python3 foo.py').startsWith("cd '/repo-root' && "),
      'selfContained() prefixes when __SR_ROOT set')
    globalThis.__SR_ROOT = undefined
    assert.strictEqual(sr.selfContained('python3 foo.py'), 'python3 foo.py',
      'selfContained() is identity when __SR_ROOT unset')
    globalThis.__SR_ROOT = '/repo-root'
    assert.strictEqual(sr.selfContained('cd /other && foo'), 'cd /other && foo',
      'selfContained() leaves cd-prefixed command untouched')
  } finally {
    globalThis.__SR_ROOT = savedRoot
  }

  console.log('OK: exec dumb-pipe + persistPhase seam (model=haiku, order, shq-quoting, fenced-string parsing, prose-prefixed shapes, FR-5 cd-prefix)')
})().catch((e) => { console.error('FAIL:', e.message || e); process.exit(1) })
