// plugins/superheroes/lib/tests/showrunner_writefile_verify_smoke.js
// #410: io.writeFile VERIFIES every courier write. The bundle preamble's writeFile was fire-and-forget
// (await __sh with no answer check, no retry, no readback), so a refused write (a courier answering
// EXEC-FAILED with zero tool calls), an empty/prose ack, a byte-mutated opaque payload, or a leaf that
// never dispatched all landed SILENTLY and the run sailed on without the file (live 2026-07-13). The
// writer now re-reads the landed file Python-side, re-hashes it with hashlib.sha256, and prints
// __SR_WROTE:<hash8> ONLY when the on-disk bytes match the hash the spine computed from the original
// content; io.writeFile checks the answer for that marker, retries EXACTLY once on the copy-faithful
// payload tier when it is missing for ANY reason, and THROWS on a second miss — never proceeding past
// an unverified write.
//
// This drives the REAL committed bundle io.writeFile through a canned agent that EXECUTES the composed
// python command against a real shell + real python3 (mirroring the engine_dispatch #257 fidelity
// smoke's real-write+verify pattern) — so the Python-side round-trip, marker, and hash-mismatch exits
// are exercised end-to-end, and the dispatch count is observed at the seam. Modes:
//   (a) happy path: faithful copy -> marker -> byte-identical on disk, EXACTLY ONE dispatch;
//   (b) refused write (EXEC-FAILED, command never ran) -> no marker -> retry -> loud throw, 2 dispatches;
//   (c) mutated payload (a byte flipped in the b64 arg) -> Python re-hash mismatch (exit 3), no marker
//       -> retry; faithful on retry CONVERGES (file correct); mutated on both -> throw;
//   (d) empty and prose-only answers -> no marker -> retry/throw;
//   (e) the composed command still contains base64.b64decode (stays in #402's _SPINE_STATE_WRITE class);
//   (f) the retry escalates to the payload tier (opts.payload) regardless of size.
// Run: node plugins/superheroes/lib/tests/showrunner_writefile_verify_smoke.js
'use strict'
const assert = require('assert')
const fs = require('fs')
const os = require('os')
const path = require('path')
const vm = require('vm')
const { execFileSync } = require('child_process')

// Run a composed shell command through a real bash + python3, returning stdout (empty on non-zero exit).
function runReal(cmd) {
  try {
    return String(execFileSync('bash', ['-c', cmd], { stdio: 'pipe', encoding: 'utf8' }) || '')
  } catch (_e) {
    return ''   // a non-zero exit (hash mismatch exit 3 / bad-b64) yields no stdout marker
  }
}

// Extract the command the writeFile leaf will run from the courier prompt (everything after the first
// blank line — the exact byte contract recordComposedFromPrompt keys off).
function commandOf(prompt) {
  const idx = String(prompt).indexOf('\n\n')
  return idx >= 0 ? String(prompt).slice(idx + 2) : String(prompt)
}

// Flip one payload byte the way the live 2026-07-13 courier did: change a single base64 char in the
// THIRD single-quoted argv token (the b64 payload) to a different but still-valid base64 char, so the
// command still parses and b64decode still succeeds — but decodes to DIFFERENT bytes whose re-hash no
// longer matches the embedded expected hash (Python exits 3).
function mutatePayloadArg(cmd) {
  const toks = cmd.match(/'(?:[^'\\]|\\.)*'/g) || []
  // tokens: [script, path, b64, hash]; mutate the b64 (index 2).
  assert.ok(toks.length >= 4, 'writeFile command must carry script/path/b64/hash argv (#410 shape)')
  const b64 = toks[2]
  const inner = b64.slice(1, -1)
  let flipped = null
  for (let i = 0; i < inner.length; i++) {
    const c = inner[i]
    if (/[A-Za-z]/.test(c)) { const r = c === 'A' ? 'B' : 'A'; flipped = inner.slice(0, i) + r + inner.slice(i + 1); break }
  }
  assert.ok(flipped && flipped !== inner, 'the payload mutation flipped a base64 byte')
  return cmd.slice(0, cmd.indexOf(b64)) + "'" + flipped + "'" + cmd.slice(cmd.indexOf(b64) + b64.length)
}

function loadBundle(dispatch) {
  const bundlePath = path.join(__dirname, '..', 'showrunner.bundle.js')
  const text = fs.readFileSync(bundlePath, 'utf8').replace(/export\s+const\s+meta/, 'const meta')
  const sandbox = { console }
  sandbox.globalThis = sandbox
  sandbox.agent = dispatch
  sandbox.parallel = async (thunks) => Promise.all((thunks || []).map((f) => f()))
  sandbox.log = () => {}
  vm.createContext(sandbox)
  vm.runInContext('globalThis.__SR_RUN = false;\n;(async () => {\n' + text + '\n})();', sandbox, { timeout: 5000 })
  return sandbox.globalThis.io
}

async function main() {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sr-410-' + process.pid + '-'))

  // ---- (a) happy path: faithful copy, EXACTLY ONE dispatch, byte-identical on disk. ----
  {
    const dispatches = []
    const io = loadBundle(async (prompt, opts) => { dispatches.push(opts || {}); return runReal(commandOf(prompt)) })
    const p = path.join(tmpDir, 'happy.json')
    const value = { hello: 'world', n: 42, arr: [1, 2, 3], uni: 'ünîcödé — 日本語' }
    await io.writeFile(p, JSON.stringify(value))
    assert.deepStrictEqual(JSON.parse(fs.readFileSync(p, 'utf8')), value, '#410 happy path: file lands byte-identical')
    assert.strictEqual(dispatches.length, 1, '#410 happy path: EXACTLY ONE dispatch (verify rides inside the write leaf, no leaf growth)')
    // (e) the composed command stays in #402's _SPINE_STATE_WRITE class (base64.b64decode substring).
    assert.ok(commandOf(await new Promise((res) => {
      loadBundle(async (prompt) => { res(prompt); return runReal(commandOf(prompt)) }).writeFile(path.join(tmpDir, 'probe.json'), 'x')
    })).includes('base64.b64decode'), '#410: the write command still contains base64.b64decode (stays in _SPINE_STATE_WRITE)')
    console.log('OK: #410 happy path writes byte-identical in exactly one dispatch, command stays base64.b64decode')
  }

  // ---- (b) refused write (EXEC-FAILED, command never ran) -> no marker -> retry -> loud throw. ----
  {
    const dispatches = []
    const io = loadBundle(async (prompt, opts) => { dispatches.push(opts || {}); return 'EXEC-FAILED' })   // never runs the command
    const p = path.join(tmpDir, 'refused.json')
    let threw = null
    try { await io.writeFile(p, JSON.stringify({ x: 1 })) } catch (e) { threw = e }
    assert.ok(threw, '#410 refused write: an unverified write THROWS (never proceeds silently)')
    assert.ok(/unverified after retry/.test(String(threw.message)), '#410 refused write: the throw names the real reason')
    assert.strictEqual(dispatches.length, 2, '#410 refused write: exactly ONE retry (2 dispatches), then throw')
    // The preamble wrapper strips the `payload` marker and resolves it to a MODEL: the cheapest courier
    // tier on the first attempt, the copy-faithful payload (fixer) tier on the escalated retry. Observing
    // the model change proves the retry rode the payload tier regardless of the small size here.
    assert.notStrictEqual(dispatches[1].model, dispatches[0].model,
      '#410 refused write: the retry escalates off the cheapest tier to the copy-faithful payload tier')
    // The first attempt rides the lean courier agent; the retry DROPS agentType (rides the default
    // full-surface dispatch) so an intermittent subagent prompt-drop degrades within the one-retry budget
    // instead of parking — mirroring __sh's prompt-drop fallback.
    assert.strictEqual(dispatches[0].agentType, 'superheroes:courier', '#410 refused write: first attempt rides the lean courier agent')
    assert.strictEqual(dispatches[1].agentType, undefined, '#410 refused write: the retry drops agentType (default full-surface dispatch)')
    assert.ok(!fs.existsSync(p), '#410 refused write: nothing landed on disk')
    console.log('OK: #410 refused (EXEC-FAILED) write retries once (payload tier, default agent) then throws loudly')
  }

  // ---- (b2) classifier denial -> deterministic -> NO retry, immediate fail-closed throw (#402 Part B). ----
  {
    const dispatches = []
    const io = loadBundle(async (prompt, opts) => { dispatches.push(opts || {}); return 'Permission for this action was denied by the auto mode classifier.' })
    let threw = null
    try { await io.writeFile(path.join(tmpDir, 'denied.json'), JSON.stringify({ x: 1 })) } catch (e) { threw = e }
    assert.ok(threw && /denied/.test(String(threw.message)), '#402 Part B: a classifier denial fails closed with the scrubbed reason')
    assert.strictEqual(dispatches.length, 1, '#402 Part B: a deterministic denial is NOT re-dispatched (re-dispatching identical bytes reads as tunneling)')
    console.log('OK: #402 Part B — a classifier denial on a write is terminal (no identical re-dispatch)')
  }

  // ---- (c) mutated payload -> Python re-hash mismatch (no marker) -> retry. ----
  {
    // mutated on BOTH attempts -> throw (never persists silently-altered content).
    const io1 = loadBundle(async (prompt) => runReal(mutatePayloadArg(commandOf(prompt))))
    const pAll = path.join(tmpDir, 'mutated-both.json')
    let threw = null
    try { await io1.writeFile(pAll, JSON.stringify({ payload: 'faithful?' })) } catch (e) { threw = e }
    assert.ok(threw, '#410 mutated payload (both attempts): a hash-mismatch write THROWS')
    // Pin that the mutation was FAITHFUL to the live specimen: valid base64 that DECODED to different bytes
    // that HIT DISK (so the Python exit-3 hash-mismatch branch fired), NOT an invalid-b64 decode crash
    // that wrote nothing. The verify caught the mismatch and the caller never trusted it — the throw is
    // the closure, not the on-disk bytes.
    assert.ok(fs.existsSync(pAll), '#410 mutated payload: the file exists')
    // __SR_W opens the file "wb" (truncating) BEFORE decode, so a decode CRASH would leave a 0-byte file;
    // a length>0 file proves b64decode succeeded and the corrupted bytes landed, so the exit-3 hash-mismatch
    // branch fired (the faithful-mutation contract), not an invalid-base64 decode crash.
    assert.ok(fs.readFileSync(pAll).length > 0, '#410 mutated payload: corrupted bytes actually landed (b64decode succeeded — a decode crash would leave a 0-byte file)')
    assert.notStrictEqual(fs.readFileSync(pAll, 'utf8'), JSON.stringify({ payload: 'faithful?' }),
      '#410 mutated payload: the on-disk bytes are the mutated (different) content — the exit-3 hash-mismatch path fired')

    // mutated on the FIRST attempt, faithful on the retry -> CONVERGES, file correct.
    let n = 0
    const io2 = loadBundle(async (prompt) => { n += 1; const c = commandOf(prompt); return runReal(n === 1 ? mutatePayloadArg(c) : c) })
    const pConv = path.join(tmpDir, 'mutated-converge.json')
    const want = { converged: true, v: 7 }
    await io2.writeFile(pConv, JSON.stringify(want))
    assert.deepStrictEqual(JSON.parse(fs.readFileSync(pConv, 'utf8')), want, '#410 mutated-then-faithful: the retry converges on the correct bytes')
    assert.strictEqual(n, 2, '#410 mutated-then-faithful: exactly one retry')
    console.log('OK: #410 a mutated base64 payload fails the Python-side hash verify -> retry (converges) / throw (persistent)')
  }

  // ---- (d) empty and prose-only answers -> no marker -> retry/throw. ----
  {
    for (const [label, answer] of [['empty', ''], ['prose', 'I wrote the file successfully for you.'], ['null', null]]) {
      const dispatches = []
      const io = loadBundle(async (prompt, opts) => { dispatches.push(opts || {}); return answer })
      let threw = null
      try { await io.writeFile(path.join(tmpDir, 'd-' + label + '.json'), JSON.stringify({ a: 1 })) } catch (e) { threw = e }
      assert.ok(threw, `#410 ${label} answer: an unverified write THROWS`)
      assert.strictEqual(dispatches.length, 2, `#410 ${label} answer: exactly one retry then throw`)
    }
    console.log('OK: #410 empty / prose-only / null answers all read as unverified -> retry then throw')
  }

  // ---- (f) a marker for the WRONG content (a stale/other hash) is not accepted. ----
  {
    const dispatches = []
    const io = loadBundle(async (prompt, opts) => { dispatches.push(opts || {}); return '__SR_WROTE:deadbeef' })   // plausible but wrong hash8
    let threw = null
    try { await io.writeFile(path.join(tmpDir, 'wrong-marker.json'), JSON.stringify({ a: 1 })) } catch (e) { threw = e }
    assert.ok(threw, '#410: a marker carrying the WRONG hash8 is not accepted (binds to the expected content hash)')
    assert.ok(/unverified after retry/.test(String(threw.message)), '#410 wrong marker: rejected through the full retry-then-throw path')
    assert.strictEqual(dispatches.length, 2, '#410 wrong marker: rejected on BOTH attempts (2 dispatches), not short-circuited')
    console.log('OK: #410 the marker is bound to the expected content hash (a wrong-hash marker is rejected on both attempts)')
  }

  // ---- (g) the 2-arg (no expected-hash) __SR_W branch stays byte-identical: plain write, exit 0, NO
  //          marker — the shape stageAndRunHelper stages through, so its `&& <helper>` chain still runs. ----
  {
    const { execFileSync } = require('child_process')
    // Reconstruct a bare 2-arg __SR_W invocation from a real writeFile command by dropping the hash argv,
    // and prove it writes byte-identical content, prints NOTHING, and exits 0 (so a chained helper runs).
    let composed = null
    await loadBundle(async (prompt) => { composed = commandOf(prompt); return runReal(commandOf(prompt)) })
      .writeFile(path.join(tmpDir, 'twoarg-src.json'), 'unused')
    const toks = composed.match(/'(?:[^'\\]|\\.)*'/g)   // [script, path, b64, hash]
    const twoArgPath = path.join(tmpDir, 'twoarg.json')
    const scriptTok = composed.slice(composed.indexOf("python3 -c '") + 'python3 -c '.length, composed.indexOf(toks[1]) - 1)
    const b64Tok = toks[2]
    const cmd2 = 'python3 -c ' + scriptTok + " '" + twoArgPath + "' " + b64Tok + '; echo __EXIT:$?'
    let out2 = ''
    try { out2 = String(execFileSync('bash', ['-c', cmd2], { stdio: 'pipe', encoding: 'utf8' }) || '') } catch (e) { out2 = 'ERR'; }
    const payloadBytes = Buffer.from(b64Tok.slice(1, -1), 'base64').toString('utf8')
    assert.strictEqual(fs.readFileSync(twoArgPath, 'utf8'), payloadBytes, '#410 2-arg __SR_W: writes byte-identical content')
    assert.ok(!out2.includes('__SR_WROTE'), '#410 2-arg __SR_W: prints NO marker (no verify branch)')
    assert.ok(/__EXIT:0\s*$/.test(out2), '#410 2-arg __SR_W: exits 0, so stageAndRunHelper\'s && <helper> chain still runs')
    console.log('OK: #410 the 2-arg (no-hash) __SR_W stage path stays byte-identical (plain write, no marker, exit 0)')
  }

  fs.rmSync(tmpDir, { recursive: true, force: true })
  console.log('ok: #410 io.writeFile verifies every courier write — faithful writes land, refused/mutated/empty/prose fail loudly')
}

main().catch((e) => { console.error('FAIL:', e.message || e, e.stack); process.exit(1) })
