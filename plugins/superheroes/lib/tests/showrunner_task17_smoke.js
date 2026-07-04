// plugins/superheroes/lib/tests/showrunner_task17_smoke.js
// TDD smoke for Task 17 (#115): startup overrides read + unconditional cheapest dumb-pipe pin.
//
// Assertions:
//   (a) startup: showrunner() issues an exec that calls model_tier_overrides.py, and the
//       parsed {role:model} map lands on globalThis.__SR_OVERRIDES; authorModel() resolves
//       through it (a concrete override like {author:'haiku'} must come back as 'haiku').
//   (b) bundle wrapper: a dumb-pipe leaf (label='exec' or label='io') ALWAYS receives
//       the cheapest model (DEFAULT_TIERS.mechanical = 'haiku') even when __SR_LEAF_MODEL
//       is set to something else (e.g. 'sonnet'). A non-dumb leaf ('lib', 'reviewer', etc.)
//       DOES get __SR_LEAF_MODEL when set. A smart leaf with neither __SR_LEAF_MODEL nor
//       opts.model receives the Opus fallback, so it can never inherit the session model.
//
// For (b): the wrapper lives in the bundle's PREAMBLE, not in showrunner.js. We evaluate the
// bundle in a vm sandbox (as showrunner_bundle_smoke.js does) and call globalThis.agent()
// directly to observe the model that is handed to the real underlying agent.
require('./_smoke_checkout_root.js')
'use strict'
const assert = require('assert')
const fs = require('fs')
const path = require('path')
const vm = require('vm')
const crypto = require('crypto')

// ---------------------------------------------------------------------------
// PART A: showrunner() startup plants __SR_OVERRIDES via exec(model_tier_overrides.py)
// ---------------------------------------------------------------------------
const sr = require('../showrunner.js')
const modelTier = require('../model_tier.js')

async function partA() {
  // Track agent calls to find the overrides exec
  const calls = []
  const savedOverrides = globalThis.__SR_OVERRIDES
  delete globalThis.__SR_OVERRIDES

  globalThis.agent = async function(prompt, opts) {
    calls.push({ prompt, opts: opts || {}, label: (opts && opts.label) || '' })
    const label = (opts && opts.label) || ''
    if (label === 'read startup state') {
      return [{ ok: true, stdout: JSON.stringify({ ok: true, spec_gate: 'passed', model_overrides: { author: 'haiku' }, doc_dir: '' }) }]
    }
    if (opts && opts.courier) {
      // Dumb-pipe leaves now carry descriptive labels ('gather snapshot'/'read gate'/…); route them
      // by the command in the prompt rather than the old bare 'exec' label.
      if (typeof prompt === 'string' && prompt.includes('recover_entry.py')) {
        // reconcile: return empty snapshot -> world_derive -> proceed
        return [{ index: 0, ok: true, stdout: JSON.stringify({
          checkpoint: null,
          world: { store_ok: true, current_content_hash: null, pr: null, seeded_empty: true },
          generation: 1,
          root: globalThis.__SR_ROOT,
        }) }]
      }
      if (typeof prompt === 'string' && prompt.includes('definition_doc.py read-gate')) {
        // readGate for spec: 'passed'
        return [{ index: 0, ok: true, stdout: '{"review":"passed"}' }]
      }
      if (typeof prompt === 'string' && prompt.includes('model_tier_overrides.py')) {
        // The startup overrides read — return a concrete override so we can verify authorModel.
        return [{ index: 0, ok: true, stdout: '{"author":"haiku"}' }]
      }
      // Any other dumb pipe: ok
      return [{ index: 0, ok: true, stdout: '{}' }]
    }
    // Park everything else (workhorse, etc.)
    return null
  }
  globalThis.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))
  globalThis.log = () => {}

  // Run showrunner; it will reconcile -> readGate(spec) -> (startup overrides read) -> runPhases
  // runPhases will park (all phases return null from agent stub) but the overrides exec must have fired.
  try {
    await sr.showrunner({ workItem: 'wi-t17' })
  } catch (_) {
    // park or exception is fine; we just want to verify the overrides exec was issued
  }

  // (a1) Startup reads overrides via the folded read startup state courier leaf.
  const ovCall = calls.find((c) => c.label === 'read startup state')
  assert.ok(ovCall, 'FAIL (a1): startup did not issue read startup state courier')
  assert.ok(ovCall.prompt.includes('model_tier_overrides'), 'FAIL (a1): startup state script loads model_tier_overrides')

  // (a2) globalThis.__SR_OVERRIDES must be set to the parsed {role:model} map
  assert.ok(
    globalThis.__SR_OVERRIDES && typeof globalThis.__SR_OVERRIDES === 'object',
    'FAIL (a2): globalThis.__SR_OVERRIDES was not set by the startup overrides exec',
  )
  assert.strictEqual(
    globalThis.__SR_OVERRIDES.author,
    'haiku',
    'FAIL (a2): __SR_OVERRIDES does not carry the parsed author override',
  )

  // (a3) authorModel() resolves through __SR_OVERRIDES (should return 'haiku' from the override)
  const am = sr.authorModel()
  assert.strictEqual(am, 'haiku', 'FAIL (a3): authorModel() did not resolve through __SR_OVERRIDES')

  // (a4) fail-safe: if the overrides exec returns invalid JSON, __SR_OVERRIDES must be {} (not crash)
  globalThis.__SR_OVERRIDES = undefined
  calls.length = 0
  let savedAgent = globalThis.agent
  globalThis.agent = async function(prompt, opts) {
    const label = (opts && opts.label) || ''
    if (label === 'read startup state') {
      return [{ ok: true, stdout: JSON.stringify({ ok: true, spec_gate: 'passed', model_overrides: 'bad', doc_dir: '' }) }]
    }
    if (opts && opts.courier) {
      if (typeof prompt === 'string' && prompt.includes('recover_entry.py')) {
        return [{ index: 0, ok: true, stdout: JSON.stringify({
          checkpoint: null,
          world: { store_ok: true, current_content_hash: null, pr: null, seeded_empty: true },
          generation: 1,
          root: globalThis.__SR_ROOT,
        }) }]
      }
      if (typeof prompt === 'string' && prompt.includes('definition_doc.py read-gate')) {
        return [{ index: 0, ok: true, stdout: '{"review":"passed"}' }]
      }
      return [{ index: 0, ok: true, stdout: '{}' }]
    }
    return null
  }
  try {
    await sr.showrunner({ workItem: 'wi-t17-fail' })
  } catch (_) {}
  assert.ok(
    globalThis.__SR_OVERRIDES !== undefined && typeof globalThis.__SR_OVERRIDES === 'object',
    'FAIL (a4): __SR_OVERRIDES was not set to {} on a failed/invalid overrides exec (should fail-safe)',
  )
  assert.strictEqual(
    Object.keys(globalThis.__SR_OVERRIDES).length,
    0,
    'FAIL (a4): __SR_OVERRIDES should be {} (empty) on invalid exec response, not crash',
  )
  globalThis.agent = savedAgent

  // Restore
  globalThis.__SR_OVERRIDES = savedOverrides
  console.log('OK (a): startup plants __SR_OVERRIDES via exec(model_tier_overrides.py); authorModel() threads it; fail-safe {} on bad parse')
}

// ---------------------------------------------------------------------------
// PART B: bundle wrapper — dumb-pipe (exec/io) always cheapest; smart gets __SR_LEAF_MODEL
// ---------------------------------------------------------------------------
async function partB() {
  const bundlePath = path.join(__dirname, '..', 'showrunner.bundle.js')
  let text = fs.readFileSync(bundlePath, 'utf8').replace(/export\s+const\s+meta/, 'const meta')

  // Track what model the real underlying agent receives for each label
  const received = []
  const sandbox = {
    console,
    args: JSON.stringify({ workItem: 'b-probe', model: 'sonnet' }),
    process: { env: {}, cwd: () => '/' },
  }
  sandbox.globalThis = sandbox
  sandbox.global = sandbox
  sandbox.agent = async function(prompt, opts) {
    received.push(Object.assign({ prompt }, opts || {}))
    if (String(prompt).includes('single-backtick-probe')) return '`{"ok":true}\n__SR_EXIT:0`'
    if (typeof sandbox.__payloadHarness === 'function') return sandbox.__payloadHarness(prompt, opts || {})
    throw new Error('STOP')  // stop after first real agent call
  }
  sandbox.parallel = async (thunks) => Promise.all((thunks || []).map((f) => f()))
  sandbox.log = () => {}
  vm.createContext(sandbox)

  // Load the bundle with __SR_RUN=false so the ENTRY does not run the showrunner; just set up globals.
  vm.runInContext('globalThis.__SR_RUN = false;\n;(async () => {\n' + text + '\n})();', sandbox, { timeout: 5000 })

  // Now manually set __SR_LEAF_MODEL to 'sonnet' (as if args.model='sonnet' was passed)
  sandbox.globalThis.__SR_LEAF_MODEL = 'sonnet'
  const cheapest = modelTier.DEFAULT_TIERS.mechanical  // 'haiku'

  // (b0) A live courier wrapped the whole helper response in a single inline backtick pair:
  // `{"ok":true}\n__SR_EXIT:0`. The marker slice leaves the leading backtick in stdout unless
  // __helperResult strips this inline wrapper too.
  received.length = 0
  const helper = await sandbox.globalThis.io.runHelper('single-backtick-probe', [])
  assert.strictEqual(helper.status, 0, 'FAIL (b0): single-backtick helper answer should preserve exit status 0')
  assert.strictEqual(helper.stdout, '{"ok":true}', 'FAIL (b0): helper stdout should strip one inline backtick wrapper')
  assert.strictEqual(
    received[0].model,
    cheapest,
    `FAIL (b0): io.runHelper must still be pinned to cheapest ('${cheapest}'), got '${received[0].model}'`,
  )

  // (b1) Call globalThis.agent with label='exec' -> wrapper must pass cheapest to __realAgent
  received.length = 0
  try { await sandbox.globalThis.agent('test exec cmd', { label: 'exec', model: cheapest }) } catch (_) {}
  assert.ok(received.length > 0, 'FAIL (b1): no call to underlying agent for exec label')
  assert.strictEqual(
    received[0].model,
    cheapest,
    `FAIL (b1): exec leaf model must be cheapest ('${cheapest}'), got '${received[0].model}' — __SR_LEAF_MODEL should NOT override exec`,
  )

  // (b2) Call globalThis.agent with label='io' -> wrapper must pass cheapest to __realAgent
  received.length = 0
  try { await sandbox.globalThis.agent('test io cmd', { label: 'io', model: cheapest }) } catch (_) {}
  assert.ok(received.length > 0, 'FAIL (b2): no call to underlying agent for io label')
  assert.strictEqual(
    received[0].model,
    cheapest,
    `FAIL (b2): io leaf model must be cheapest ('${cheapest}'), got '${received[0].model}' — __SR_LEAF_MODEL should NOT override io`,
  )

  // (b3) Call globalThis.agent with label='lib' (non-dumb) -> wrapper must apply __SR_LEAF_MODEL
  received.length = 0
  try { await sandbox.globalThis.agent('test lib cmd', { label: 'lib' }) } catch (_) {}
  assert.ok(received.length > 0, 'FAIL (b3): no call to underlying agent for lib label')
  assert.strictEqual(
    received[0].model,
    'sonnet',
    `FAIL (b3): lib leaf model must be __SR_LEAF_MODEL='sonnet', got '${received[0].model}'`,
  )

  // (b4) __SR_LEAF_MODEL keeps throwaway-run precedence even over an explicitly-pinned smart leaf.
  received.length = 0
  try { await sandbox.globalThis.agent('test explicit smart override', { label: 'reviewer:r1', model: 'opus' }) } catch (_) {}
  assert.ok(received.length > 0, 'FAIL (b4): no call to underlying agent for explicit smart leaf')
  assert.strictEqual(
    received[0].model,
    'sonnet',
    `FAIL (b4): __SR_LEAF_MODEL must override explicit smart opts.model, got '${received[0].model}'`,
  )

  // (b5) No __SR_LEAF_MODEL set + explicit smart opts.model: preserve the caller's pin.
  sandbox.globalThis.__SR_LEAF_MODEL = null
  received.length = 0
  try { await sandbox.globalThis.agent('test explicit smart pin', { label: 'reviewer:r1', model: 'opus' }) } catch (_) {}
  assert.ok(received.length > 0, 'FAIL (b5): no call to underlying agent for explicit reviewer label')
  assert.strictEqual(
    received[0].model,
    'opus',
    `FAIL (b5): explicit smart opts.model should be preserved without __SR_LEAF_MODEL, got '${received[0].model}'`,
  )

  // (b6) No __SR_LEAF_MODEL set + no opts.model: smart leaf gets the Opus fallback.
  received.length = 0
  try { await sandbox.globalThis.agent('test lib no-override', { label: 'reviewer:r1' }) } catch (_) {}
  assert.ok(received.length > 0, 'FAIL (b6): no call to underlying agent for reviewer label')
  assert.strictEqual(
    received[0].model,
    modelTier.DEFAULT_TIERS.synthesis,
    `FAIL (b6): smart leaf without opts.model must fall back to Opus, got '${received[0].model}'`,
  )

  // (b7) Even with no opts at all, exec label should still get cheapest
  sandbox.globalThis.__SR_LEAF_MODEL = 'sonnet'
  received.length = 0
  try { await sandbox.globalThis.agent('test exec no-opts', { label: 'exec' }) } catch (_) {}
  assert.ok(received.length > 0, 'FAIL (b7): no call to underlying agent for exec with no opts')
  assert.strictEqual(
    received[0].model,
    cheapest,
    `FAIL (b7): exec with no prior model in opts must still get cheapest ('${cheapest}'), got '${received[0].model}'`,
  )

  // (b8) The NEW routing contract: a descriptively-labelled dumb pipe (e.g. 'read gate') marked
  // courier:true is pinned to the cheapest model too — the marker, not the bare 'exec' string, is
  // what identifies a dumb pipe — and __SR_LEAF_MODEL never overrides it.
  sandbox.globalThis.__SR_LEAF_MODEL = 'sonnet'
  received.length = 0
  try { await sandbox.globalThis.agent('read gate cmd', { label: 'read gate', courier: true, model: 'opus' }) } catch (_) {}
  assert.ok(received.length > 0, 'FAIL (b8): no call to underlying agent for a descriptive courier leaf')
  assert.strictEqual(
    received[0].model,
    cheapest,
    `FAIL (b8): a descriptive courier leaf must get cheapest ('${cheapest}'), got '${received[0].model}' — courier:true pins it regardless of label/__SR_LEAF_MODEL`,
  )
  assert.strictEqual(received[0].label, 'read gate', 'FAIL (b8): the descriptive label is preserved for display (not relabelled)')
  assert.ok(!('courier' in received[0]), 'FAIL (b8): the courier marker is stripped before the real agent() call')


  // (b9) Payload-carrying dumb pipes are still couriers, but they must use a copy-faithful fixer tier
  // rather than the cheapest mechanical tier.
  sandbox.globalThis.__SR_LEAF_MODEL = 'haiku'
  received.length = 0
  try { await sandbox.globalThis.agent('stage payload chunk', { label: 'io', courier: true, payload: true }) } catch (_) {}
  assert.ok(received.length > 0, 'FAIL (b9): no call to underlying agent for payload courier')
  assert.strictEqual(
    received[0].model,
    modelTier.DEFAULT_TIERS.fixer,
    `FAIL (b9): payload courier must use fixer tier ('${modelTier.DEFAULT_TIERS.fixer}'), got '${received[0].model}'`,
  )

  // (b10) The live bundle path for oversized stageAndRunHelper payloads chunks, verifies,
  // reassembles, and runs the helper against the exact original payload.
  function sha(text) {
    return crypto.createHash('sha256').update(String(text), 'utf8').digest('hex')
  }
  function commandFromPrompt(prompt) {
    const text = String(prompt || '')
    const idx = text.lastIndexOf('\n\n')
    return idx >= 0 ? text.slice(idx + 2) : text
  }
  function argValue(cmd, flag) {
    const match = String(cmd).match(new RegExp("'" + flag + "'\\s+'([^']*)'"))
    return match ? match[1] : null
  }
  const staged = Object.create(null)
  const partsByPath = Object.create(null)
  const stageCalls = []
  const finishCalls = []
  sandbox.__payloadHarness = async function(prompt) {
    const cmd = commandFromPrompt(prompt)
    const current = received[received.length - 1]
    if (cmd.includes("'stage-chunk'")) {
      assert.strictEqual(current.model, modelTier.DEFAULT_TIERS.fixer, 'FAIL (b10): stage-chunk courier must use fixer tier')
      const target = argValue(cmd, '--path')
      const index = Number(argValue(cmd, '--index'))
      const total = Number(argValue(cmd, '--total'))
      const b64 = argValue(cmd, '--chunk-b64')
      const hash = argValue(cmd, '--chunk-hash')
      assert.strictEqual(sha(b64), hash, 'FAIL (b10): stage-chunk hash must cover the base64 chunk')
      const bucket = partsByPath[target] || (partsByPath[target] = { total, chunks: [] })
      bucket.chunks[index] = Buffer.from(b64, 'base64').toString('utf8')
      stageCalls.push({ target, index, total })
      return JSON.stringify({ ok: true, index, total }) + '\n__SR_EXIT:0'
    }
    if (cmd.includes("'finish-chunks'")) {
      assert.strictEqual(current.model, modelTier.DEFAULT_TIERS.fixer, 'FAIL (b10): finish/helper courier must use fixer tier')
      const target = argValue(cmd, '--path')
      const total = Number(argValue(cmd, '--total'))
      const payloadHash = argValue(cmd, '--payload-hash')
      const bucket = partsByPath[target]
      assert.ok(bucket, 'FAIL (b10): finish-chunks ran before any chunks were staged')
      assert.strictEqual(bucket.chunks.length, total, 'FAIL (b10): finish-chunks total must match staged chunks')
      const text = bucket.chunks.join('')
      assert.strictEqual(sha(text), payloadHash, 'FAIL (b10): finish-chunks hash must cover the assembled payload')
      // The mock fabricates the helper's stdout from its own bucket, so this branch would pass
      // even if the bundle forgot to chain the helper. Pin the COMMAND SHAPE: the helper must be
      // chained after a verified finish, with the exit marker last.
      const helperSegment = " >/dev/null && 'cat' '" + target + "' 2>&1; echo __SR_EXIT:$?"
      assert.ok(cmd.endsWith(helperSegment),
        'FAIL (b10): finish-chunks must gate the chained helper on a verified finish, got: ' + cmd.slice(-160))
      staged[target] = text
      finishCalls.push({ target, total })
      return staged[target] + '\n__SR_EXIT:0'
    }
    throw new Error('unexpected payload courier command: ' + cmd)
  }
  sandbox.globalThis.__SR_LEAF_MODEL = 'haiku'
  received.length = 0
  const stagedPath = '/tmp/staged-large-payload.txt'
  const payload = ('chunked payload \u2014 \u{1f3a1} ' + 'x'.repeat(1800) + '\n').repeat(3)
  const result = await sandbox.globalThis.io.stageAndRunHelper(stagedPath, payload, 'cat', [stagedPath])
  assert.strictEqual(result.ok, true, 'FAIL (b10): oversized stageAndRunHelper should report a clean helper exit')
  assert.strictEqual(result.stdout, payload, 'FAIL (b10): helper must see the exact staged payload')
  assert.ok(stageCalls.length > 1, 'FAIL (b10): oversized payload must be split across multiple stage-chunk calls')
  assert.strictEqual(finishCalls.length, 1, 'FAIL (b10): finish-chunks must run exactly once before the helper')
  assert.ok(received.every((c) => c.model === modelTier.DEFAULT_TIERS.fixer), 'FAIL (b10): every oversized payload courier call must use fixer tier')
  sandbox.__payloadHarness = null

  // (b11) io.runHelper forwards the payload marker (#191): a receipt-fetch (read-chunk) answer
  // is a ~2KB relay payload and must ride the copy-faithful fixer tier; b0 already pins the
  // plain (opt-less) runHelper to cheapest.
  received.length = 0
  try { await sandbox.globalThis.io.runHelper('python3', ['read_chunk_probe.py'], { payload: true }) } catch (_) {}
  assert.ok(received.length > 0, 'FAIL (b11): no call to underlying agent for payload runHelper')
  assert.strictEqual(
    received[0].model,
    modelTier.DEFAULT_TIERS.fixer,
    `FAIL (b11): payload-marked runHelper must use fixer tier ('${modelTier.DEFAULT_TIERS.fixer}'), got '${received[0].model}'`,
  )

  console.log('OK (b): bundle wrapper — exec/io + courier:true model pinning, payload courier fixer tier, smart leaves get __SR_LEAF_MODEL')
}

// ---------------------------------------------------------------------------
// PART C (#194): the lean courier agent — every dumb-pipe (__sh) leaf dispatches on
// agentType 'superheroes:courier'; the __SR_EXIT prompt-drop guard retries once then falls
// back to the DEFAULT dispatch; a smart (non-courier) leaf never carries agentType.
// ---------------------------------------------------------------------------
async function partC() {
  const bundlePath = path.join(__dirname, '..', 'showrunner.bundle.js')
  const text = fs.readFileSync(bundlePath, 'utf8').replace(/export\s+const\s+meta/, 'const meta')

  const received = []
  let answerFn = null
  const sandbox = {
    console,
    args: JSON.stringify({ workItem: 'c-probe', model: 'sonnet' }),
    process: { env: {}, cwd: () => '/' },
  }
  sandbox.globalThis = sandbox
  sandbox.global = sandbox
  sandbox.agent = async function(prompt, opts) {
    received.push(Object.assign({ prompt }, opts || {}))
    // answerFn drives the guard: return a marker-less answer to simulate a prompt-drop, or a
    // marker-carrying one for the healthy path. Default: a clean marker answer.
    return answerFn ? answerFn(received.length, prompt, opts) : '__SR_EXIT:0'
  }
  sandbox.parallel = async (thunks) => Promise.all((thunks || []).map((f) => f()))
  sandbox.log = () => {}
  vm.createContext(sandbox)
  vm.runInContext('globalThis.__SR_RUN = false;\n;(async () => {\n' + text + '\n})();', sandbox, { timeout: 5000 })
  const cheapest = modelTier.DEFAULT_TIERS.mechanical

  // (c1) A healthy courier leaf (io.runHelper -> __sh) carries agentType 'superheroes:courier',
  // dispatches exactly once, keeps the cheapest-model pin, and the courier marker is still stripped.
  received.length = 0
  answerFn = () => '{"ok":true}\n__SR_EXIT:0'
  const c1 = await sandbox.globalThis.io.runHelper('probe', [])
  assert.strictEqual(c1.status, 0, 'FAIL (c1): healthy helper answer should read exit status 0')
  assert.strictEqual(received.length, 1, 'FAIL (c1): a healthy marker-carrying leaf must dispatch exactly once')
  assert.strictEqual(
    received[0].agentType,
    'superheroes:courier',
    `FAIL (c1): a courier leaf must carry agentType 'superheroes:courier', got '${received[0].agentType}'`,
  )
  assert.strictEqual(received[0].model, cheapest, 'FAIL (c1): agentType must not disturb the cheapest-model pin')
  assert.ok(!('courier' in received[0]), 'FAIL (c1): the courier marker is still stripped before the real agent() call')

  // (c2) A smart (non-courier) leaf NEVER carries agentType — the lean courier agent is a dumb-pipe
  // concern only, so smart reviewers/fixers keep the full tool surface.
  received.length = 0
  answerFn = () => 'noop'
  try { await sandbox.globalThis.agent('review something', { label: 'reviewer:r1', model: 'opus' }) } catch (_) {}
  assert.ok(received.length > 0, 'FAIL (c2): no call to underlying agent for smart leaf')
  assert.ok(!('agentType' in received[0]), `FAIL (c2): a smart leaf must NOT carry agentType, got '${received[0].agentType}'`)

  // (c3) Prompt-drop guard: two marker-less answers -> retry once on the courier agent, then fall back
  // to the DEFAULT dispatch (agentType dropped) so a dispatch bug degrades to today's cost, never a
  // park. The cheapest-model pin (courier:true) survives the fallback.
  received.length = 0
  answerFn = (n) => (n <= 2 ? 'EXEC-FAILED' : '{"ok":true}\n__SR_EXIT:0')
  const c3 = await sandbox.globalThis.io.runHelper('drop-probe', [])
  assert.strictEqual(received.length, 3, 'FAIL (c3): two marker-less answers must produce retry + fallback = 3 dispatches')
  assert.strictEqual(received[0].agentType, 'superheroes:courier', 'FAIL (c3): first dispatch is on the courier agent')
  assert.strictEqual(received[1].agentType, 'superheroes:courier', 'FAIL (c3): the retry stays on the courier agent')
  assert.ok(!('agentType' in received[2]), 'FAIL (c3): the fallback drops agentType (default dispatch)')
  assert.strictEqual(received[2].model, cheapest, 'FAIL (c3): the fallback keeps the cheapest-model pin (courier:true retained)')
  assert.strictEqual(c3.ok, true, 'FAIL (c3): the fallback answer (marker-carrying) is parsed as a clean exit')

  // (c4) A NON-marker courier leaf (mkdir) still carries agentType but is NOT subject to the guard
  // (there is no marker to check), so it dispatches exactly once even on a marker-less answer — a
  // regression guard against the fallback loop firing on every leaf.
  received.length = 0
  answerFn = () => 'ok'
  await sandbox.globalThis.io.mkdirp('/tmp/c4-probe')
  assert.strictEqual(received.length, 1, 'FAIL (c4): a non-marker courier leaf must dispatch once (no marker guard)')
  assert.strictEqual(received[0].agentType, 'superheroes:courier', 'FAIL (c4): a non-marker courier leaf still carries agentType')

  // (c5) Echo-back blind spot (#194 review): a leaf that echoes the command back WITHOUT running it
  // returns text carrying the LITERAL unexpanded '__SR_EXIT:$?' — the marker STRING is present, so a
  // bare presence check would wrongly pass. The guard must treat this as a failed dispatch too:
  // retry once, then fall back to the default dispatch, exactly like a marker-less answer.
  received.length = 0
  answerFn = (n) => (n <= 2
    ? "cd '/repo' && 'echo-probe' 2>&1; echo __SR_EXIT:$?"   // command echoed back, $? unexpanded
    : '{"ok":true}\n__SR_EXIT:0')
  const c5 = await sandbox.globalThis.io.runHelper('echo-probe', [])
  assert.strictEqual(received.length, 3, 'FAIL (c5): an echoed-command answer must retry + fall back = 3 dispatches')
  assert.strictEqual(received[0].agentType, 'superheroes:courier', 'FAIL (c5): first dispatch is on the courier agent')
  assert.strictEqual(received[1].agentType, 'superheroes:courier', 'FAIL (c5): the retry stays on the courier agent')
  assert.ok(!('agentType' in received[2]), 'FAIL (c5): the fallback drops agentType (default dispatch)')
  assert.strictEqual(c5.ok, true, 'FAIL (c5): the fallback answer (real marker) parses as a clean exit')

  // (c6) Dispatch REJECTION fallback (live 2026-07-04, run wf_b408ece1-0ed): on a plugin cache
  // older than the courier agent, agent() REJECTS with "agent type 'superheroes:courier' not
  // found" — a THROW the __SR_EXIT answer guard never sees (it only inspects returned answers).
  // The wrapper must catch exactly that rejection at the dispatch choke-point and re-dispatch
  // ONCE without agentType. Fresh sandbox: __realAgent is captured at bundle eval, so the
  // rejecting agent must be installed BEFORE the eval. Covers BOTH leaf shapes: a non-marker
  // leaf (mkdir — the run-29 test-pilot writeStatus crash class) and a marker leaf (runHelper).
  const sandbox2 = {
    console, args: JSON.stringify({ workItem: 'c-probe-2', model: 'sonnet' }),
    process: { env: {}, cwd: () => '/' },
  }
  sandbox2.globalThis = sandbox2
  sandbox2.global = sandbox2
  const received2 = []
  let rejectMode = 'not-found'
  sandbox2.agent = async function(prompt, opts) {
    received2.push(Object.assign({ prompt }, opts || {}))
    if (opts && opts.agentType) {
      if (rejectMode === 'not-found') {
        throw new Error("agent type 'superheroes:courier' not found. Available agents: claude, general-purpose")
      }
      throw new Error('rate limited — try again')
    }
    return '{"ok":true}\n__SR_EXIT:0'
  }
  sandbox2.parallel = async (thunks) => Promise.all((thunks || []).map((f) => f()))
  sandbox2.log = () => {}
  vm.createContext(sandbox2)
  vm.runInContext('globalThis.__SR_RUN = false;\n;(async () => {\n' + text + '\n})();', sandbox2, { timeout: 5000 })

  received2.length = 0
  await sandbox2.globalThis.io.mkdirp('/tmp/c6-probe')          // non-marker leaf: run-29's crash shape
  assert.strictEqual(received2.length, 2, 'FAIL (c6): a not-found rejection must re-dispatch exactly once')
  assert.strictEqual(received2[0].agentType, 'superheroes:courier', 'FAIL (c6): first dispatch carries agentType')
  assert.ok(!('agentType' in received2[1]), 'FAIL (c6): the fallback re-dispatch drops agentType')
  assert.strictEqual(received2[1].model, cheapest, 'FAIL (c6): the fallback keeps the cheapest-model pin')

  received2.length = 0
  const c6h = await sandbox2.globalThis.io.runHelper('c6-helper-probe', [])
  assert.strictEqual(c6h.status, 0, 'FAIL (c6): a marker leaf must parse the fallback answer cleanly')
  assert.strictEqual(received2.length, 2, 'FAIL (c6): marker leaf — not-found rejection means 2 dispatches (no extra marker retries)')
  assert.ok(!('agentType' in received2[1]), 'FAIL (c6): marker-leaf fallback drops agentType')

  // (c7) Any OTHER rejection with agentType present must PROPAGATE — the fallback is scoped to
  // the not-found shape only, never a blanket swallow of dispatch errors.
  rejectMode = 'other'
  received2.length = 0
  let c7threw = null
  try { await sandbox2.globalThis.io.mkdirp('/tmp/c7-probe') } catch (e) { c7threw = e }
  assert.ok(c7threw && /rate limited/.test(String((c7threw && c7threw.message) || c7threw)),
    'FAIL (c7): a non-not-found rejection must propagate, not silently fall back')
  assert.strictEqual(received2.length, 1, 'FAIL (c7): no fallback re-dispatch for a non-not-found rejection')

  console.log('OK (c): courier leaves dispatch on superheroes:courier; guard (missing + echoed marker) falls back to default; a not-found dispatch REJECTION falls back at the wrapper; smart leaves never carry it')
}

;(async () => {
  await partA()
  await partB()
  await partC()
  console.log('OK: Task 17 — startup __SR_OVERRIDES + unconditional cheapest dumb-pipe (bundle wrapper) + lean courier agent (#194)')
})().catch((e) => { console.error('FAIL:', e.message || e, e.stack); process.exit(1) })
