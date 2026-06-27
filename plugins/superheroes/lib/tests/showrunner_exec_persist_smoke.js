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

  // ---- (b) persistPhase: journal BEFORE checkpoint; {ok:true} on success ----
  calls.length = 0
  // Reset agent to record multi-command batch call.
  globalThis.agent = async (prompt, opts) => {
    calls.push({ prompt, opts: opts || {} })
    // Three entries: sideEffect=0, journal=1, checkpoint=2
    return [
      { index: 0, ok: true, stdout: 'side-ok' },
      { index: 1, ok: true, stdout: 'journal-ok' },
      { index: 2, ok: true, stdout: 'checkpoint-ok' },
    ]
  }

  const payload = { phase: 'plan', gate: 'passed', confidence: 'high', assumptions: [] }
  const ok = await sr.persistPhase('wi-test', {
    sideEffectCmd: 'echo side-effect',
    journalPayload: payload,
    step: 3,
    phase: 'review-plan',
  })
  assert.strictEqual(calls.length, 1, 'persistPhase dispatches exactly one exec (one agent call)')
  const pp = calls[0].prompt
  // journal_entry must appear before checkpoint_entry in the prompt.
  const journalIdx = pp.indexOf('journal_entry')
  const checkpointIdx = pp.indexOf('checkpoint_entry')
  assert.ok(journalIdx >= 0, 'prompt contains journal_entry')
  assert.ok(checkpointIdx >= 0, 'prompt contains checkpoint_entry')
  assert.ok(journalIdx < checkpointIdx, 'journal_entry appears before checkpoint_entry in the batched prompt')
  // sideEffectCmd appears before journal_entry (side-effect leads).
  const sideIdx = pp.indexOf('echo side-effect')
  assert.ok(sideIdx >= 0, 'prompt contains the sideEffectCmd')
  assert.ok(sideIdx < journalIdx, 'sideEffectCmd appears before journal_entry')
  assert.deepStrictEqual(ok, { ok: true }, 'persistPhase returns {ok:true} when all results ok')

  // ---- (b) persistPhase: {ok:false} when any command fails ----
  calls.length = 0
  globalThis.agent = async (prompt, opts) => {
    calls.push({ prompt, opts: opts || {} })
    return [
      { index: 0, ok: true, stdout: 'journal-ok' },
      { index: 1, ok: false, stdout: '' },  // checkpoint failed
    ]
  }
  const fail = await sr.persistPhase('wi-test', {
    journalPayload: { phase: 'plan' },
    step: 2,
    phase: 'plan',
  })
  assert.deepStrictEqual(fail, { ok: false }, 'persistPhase returns {ok:false} when any result fails')

  // ---- (c) shq-quoting: no raw unquoted JSON in the prompt ----
  calls.length = 0
  const jsonPayload = { phase: 'review-plan', gate: 'passed', confidence: 'high', assumptions: ['x'] }
  globalThis.agent = async (prompt, opts) => {
    calls.push({ prompt, opts: opts || {} })
    return [{ index: 0, ok: true, stdout: '' }, { index: 1, ok: true, stdout: '' }]
  }
  await sr.persistPhase('wi-q', {
    journalPayload: jsonPayload,
    step: 5,
    phase: 'review-plan',
  })
  assert.strictEqual(calls.length, 1, 'persistPhase (no sideEffect) makes exactly one exec call')
  const qp = calls[0].prompt
  // The JSON payload must be shell-quoted (starts with single quote) before the JSON open-brace.
  // Raw form would be: --payload {"phase":...} (quote-free brace immediately after the flag).
  // Quoted form:        --payload '{"phase":...}' (brace inside single quotes).
  // Verify no naked `--payload {` (raw unquoted JSON arg).
  assert.ok(!qp.includes("--payload {"), 'journal_entry --payload is shq-quoted (no raw {')
  assert.ok(qp.includes("--payload '"), "journal_entry --payload arg is single-quoted by shq")
  // Likewise --step and --phase must be single-quoted.
  assert.ok(qp.includes("--step '"), '--step arg is shq-quoted')
  assert.ok(qp.includes("--phase '"), '--phase arg is shq-quoted')

  console.log('OK: exec dumb-pipe + persistPhase seam (model=haiku, order, shq-quoting)')
})().catch((e) => { console.error('FAIL:', e.message || e); process.exit(1) })
