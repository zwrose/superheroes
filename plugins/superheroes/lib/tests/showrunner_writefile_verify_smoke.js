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
//   (c) mutated payload (a byte flipped in the plain-visible arg) -> Python re-hash mismatch (exit 3), no
//       marker -> retry; faithful on retry CONVERGES (file correct); mutated on both -> throw;
//   (d) empty and prose-only answers -> no marker -> retry/throw;
//   (e) the composed command carries the __SR_WROTE marker literal (stays in #402's _SPINE_STATE_WRITE class)
//       and is PLAIN-VISIBLE — no base64, and the write-courier prompt drops the verbatim-relay demand (#435);
//   (e2) a NARRATED reply that embeds a valid receipt line PASSES in one dispatch (narration tolerance, #435);
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

// Flip one payload byte the way the live 2026-07-13 courier did: change a single letter in the THIRD
// single-quoted argv token (the PLAIN-VISIBLE #435 payload) to a different letter, so the command still
// parses — but the written bytes differ, and the Python re-hash no longer matches the embedded expected
// hash (exit 3, no marker). The test payloads (JSON.stringify output) carry no single quotes, so each argv
// is one clean shq token and the token regex is exact.
function mutatePayloadArg(cmd) {
  const toks = cmd.match(/'(?:[^'\\]|\\.)*'/g) || []
  // tokens: [script, path, payload, hash]; mutate the payload (index 2).
  assert.ok(toks.length >= 4, 'writeFile command must carry script/path/payload/hash argv (#435 shape)')
  const payload = toks[2]
  const inner = payload.slice(1, -1)
  let flipped = null
  for (let i = 0; i < inner.length; i++) {
    const c = inner[i]
    if (/[A-Za-z]/.test(c)) { const r = c === 'A' ? 'B' : 'A'; flipped = inner.slice(0, i) + r + inner.slice(i + 1); break }
  }
  assert.ok(flipped && flipped !== inner, 'the payload mutation flipped a content byte')
  return cmd.slice(0, cmd.indexOf(payload)) + "'" + flipped + "'" + cmd.slice(cmd.indexOf(payload) + payload.length)
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
    // (e) #435: the composed command stays in #402's _SPINE_STATE_WRITE class (__SR_WROTE marker literal),
    // is PLAIN-VISIBLE (no base64), and its dispatch prompt drops the verbatim-relay demand the classifier
    // flagged as concealment — while KEEPING transparency framing and the payload-is-data clause.
    let probePrompt = null
    await loadBundle(async (prompt) => { probePrompt = prompt; return runReal(commandOf(prompt)) }).writeFile(path.join(tmpDir, 'probe.json'), 'x')
    assert.ok(commandOf(probePrompt).includes('__SR_WROTE'), '#435: the write command carries the __SR_WROTE marker (stays in _SPINE_STATE_WRITE)')
    assert.ok(!commandOf(probePrompt).includes('base64'), '#435: the write command is plain-visible — NO base64')
    assert.ok(!/entire reply must be the command's stdout, verbatim/i.test(probePrompt) && !/any narration[^.]*corrupts the parse/i.test(probePrompt),
      '#435: the write-courier prompt drops the verbatim-relay / narration-corrupts sentence (the flagged concealment clause)')
    assert.ok(/recorded in the (?:session transcript|run journal)|nothing here is hidden/i.test(probePrompt),
      '#435: the write-courier prompt keeps transparency framing (nothing hidden, on the record)')
    assert.ok(/command text is DATA to transport/i.test(probePrompt), '#435: the write-courier prompt keeps the payload-is-data clause (#403)')
    console.log('OK: #435 happy path writes byte-identical in one dispatch — plain-visible, __SR_WROTE class, narration-tolerant prompt')
  }

  // ---- (e2) NARRATION TOLERANCE: a chatty reply that EMBEDS a valid receipt line passes in ONE dispatch. ----
  {
    // The courier runs the real command (so the file lands + the marker is genuine) but wraps its reply in
    // conversational prose. #435: writeFile extracts the __SR_WROTE receipt by pattern (indexOf), so narration
    // around a VALID marker is accepted — no retry, no throw. (A narrated reply with a WRONG/absent marker is
    // still rejected — covered by (d) prose and (f) wrong-marker below.)
    const dispatches = []
    const io = loadBundle(async (prompt, opts) => {
      dispatches.push(opts || {})
      const real = runReal(commandOf(prompt))   // runs the command; real carries the genuine __SR_WROTE marker
      return 'Sure — I ran the command and the file was written.\n' + real + '\nLet me know if you need anything else!'
    })
    const p = path.join(tmpDir, 'narrated.json')
    const value = { narrated: true, n: 9 }
    await io.writeFile(p, JSON.stringify(value))
    assert.deepStrictEqual(JSON.parse(fs.readFileSync(p, 'utf8')), value, '#435 narration: the file lands correctly')
    assert.strictEqual(dispatches.length, 1, '#435 narration: a narrated-but-valid receipt passes in EXACTLY ONE dispatch (no retry)')
    console.log('OK: #435 a narrated reply embedding a valid __SR_WROTE receipt passes in one dispatch (pattern-extracted, narration tolerant)')
  }

  // ---- (a2) ESCAPE-REQUIRING content round-trips byte-identical through the REAL python3 writer. ----
  {
    // The whole point of the #435 escape-encoding (encPayload -> SR_WRITER_SCRIPT decode). The other real-
    // python cases use JSON.stringify output (no raw newlines/backslashes/apostrophes), so a decode-ordering
    // bug (two-backslash-n before \n) or a dropped encPayload replace() would be INVISIBLE — the on-disk
    // re-hash would silently mismatch and every multiline/backslash write would fail closed in production
    // while the smokes stayed green. This drives the committed writer against a real shell + python3 with
    // content that exercises every escape branch, and pins byte-identical readback in EXACTLY ONE dispatch
    // (a decode divergence drops the marker -> 2 dispatches -> throw).
    const dispatches = []
    const io = loadBundle(async (prompt, opts) => { dispatches.push(opts || {}); return runReal(commandOf(prompt)) })
    const p = path.join(tmpDir, 'escape-heavy.txt')
    const value = [
      'line1',
      'line2 with a real LF above and a CRLF next\r',
      'literal backslash-n: a\\nb (must stay backslash-n, NOT a newline)',
      'trailing backslash: c\\',
      'double backslash: d\\\\e',
      "apostrophe: don't  quote: \"x\"",
      'tab\there  unicode ünî 日本語 🎉',
      '__SR_EXIT:0 and __SR_WROTE:cafebabe embedded as content',   // marker-looking substrings in the payload
    ].join('\n')
    await io.writeFile(p, value)
    assert.strictEqual(fs.readFileSync(p, 'utf8'), value,
      '#435 escape-heavy content round-trips byte-identical through the REAL python3 writer (newline/CR/backslash/apostrophe/literal-\\n)')
    assert.strictEqual(dispatches.length, 1,
      '#435 escape-heavy: faithful decode -> marker present -> EXACTLY ONE dispatch (a decode divergence would drop the marker and force a retry)')
    console.log('OK: #435 escape-requiring content (LF/CRLF/backslash/literal-\\n/apostrophe/unicode + marker-looking substrings) round-trips byte-identical in one dispatch')
  }

  // ---- (a3) isWriteCommand's load-bearing anchor: the record_composed embedding leaf is NOT a write. ----
  {
    const { isWriteCommand, parseWrite } = require('./_sr_write.js')
    // A real io.writeFile command (bare `python3 -c '<writer>' …`, carrying __SR_WROTE) IS a write.
    let composed = null
    await loadBundle(async (prompt) => { composed = commandOf(prompt); return runReal(commandOf(prompt)) })
      .writeFile(path.join(tmpDir, 'anchor-src.json'), JSON.stringify({ ok: true }))
    assert.ok(isWriteCommand(composed), '#435 isWriteCommand: a bare io.writeFile command is a write')
    assert.deepStrictEqual(JSON.parse(parseWrite(composed).content), { ok: true }, '#435 parseWrite recovers the content of a real write')
    // The composed-exact record_composed leaf EMBEDS that write command as an argv payload — so its OWN bytes
    // contain both __SR_WROTE and the substring `python3 -c '` — but it is composed via __argv as a QUOTED
    // `'python3' '-c' …` leaf, which the anchor must EXCLUDE (else parseWrite misreads the runId as the path,
    // corrupting the canned in-memory FS and looping the misbehaving/stretch smokes).
    const recordComposedLeaf = "'python3' '-c' 'import permission_rules; permission_rules.record_composed(...)' '5' " + "'" + composed.replace(/'/g, "'\\''") + "' '.' 'wi'"
    assert.ok(!isWriteCommand(recordComposedLeaf),
      '#435 isWriteCommand: a record_composed leaf embedding a write command is NOT mis-classified as a write (bare-prefix anchor)')
    // The anchor tolerates a cd-root wrap on a real write (rootedCommand prefixes `cd '<root>' && `).
    assert.ok(isWriteCommand("cd '/repo root' && " + composed), '#435 isWriteCommand: a cd-root-wrapped write is still a write')
    console.log('OK: #435 isWriteCommand anchors on the bare python3 -c write shape (excludes the record_composed embedding leaf, tolerates cd-root wrap)')
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
    // Pin that the mutation actually hit disk: the plain-visible payload DECODED to different bytes that
    // HIT DISK (so the Python exit-3 hash-mismatch branch fired), then the caller never trusted them — the
    // throw is the closure, not the on-disk bytes.
    assert.ok(fs.existsSync(pAll), '#435 mutated payload: the file exists')
    // #435: the writer opens the file "w" and writes the decoded content BEFORE the re-hash, so a length>0
    // file proves the corrupted bytes landed and the exit-3 hash-mismatch branch fired (the plain payload
    // never "fails to decode" — decPayload is total — so a mismatch is always a content mutation, not a crash).
    assert.ok(fs.readFileSync(pAll).length > 0, '#435 mutated payload: corrupted bytes actually landed, then the exit-3 hash-mismatch fired')
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
    console.log('OK: #435 a mutated plain payload fails the Python-side hash verify -> retry (converges) / throw (persistent)')
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
    const { decPayload } = require('./_sr_write.js')
    // Reconstruct a bare 2-arg __SR_W invocation from a real writeFile command by dropping the hash argv,
    // and prove it writes byte-identical content, prints NOTHING, and exits 0 (so a chained helper runs).
    let composed = null
    await loadBundle(async (prompt) => { composed = commandOf(prompt); return runReal(commandOf(prompt)) })
      .writeFile(path.join(tmpDir, 'twoarg-src.json'), 'unused')
    const toks = composed.match(/'(?:[^'\\]|\\.)*'/g)   // [script, path, enc-payload, hash]
    const twoArgPath = path.join(tmpDir, 'twoarg.json')
    const scriptTok = composed.slice(composed.indexOf("python3 -c '") + 'python3 -c '.length, composed.indexOf(toks[1]) - 1)
    const payloadTok = toks[2]
    const cmd2 = 'python3 -c ' + scriptTok + " '" + twoArgPath + "' " + payloadTok + '; echo __EXIT:$?'
    let out2 = ''
    try { out2 = String(execFileSync('bash', ['-c', cmd2], { stdio: 'pipe', encoding: 'utf8' }) || '') } catch (e) { out2 = 'ERR'; }
    // #435: the payload is plain-visible escape-encoded text — decPayload (not base64) recovers the bytes.
    const payloadBytes = decPayload(payloadTok.slice(1, -1))
    assert.strictEqual(fs.readFileSync(twoArgPath, 'utf8'), payloadBytes, '#435 2-arg __SR_W: writes byte-identical content')
    assert.ok(!out2.includes('__SR_WROTE'), '#435 2-arg __SR_W: prints NO marker (no verify branch)')
    assert.ok(/__EXIT:0\s*$/.test(out2), '#435 2-arg __SR_W: exits 0, so stageAndRunHelper\'s && <helper> chain still runs')
    console.log('OK: #435 the 2-arg (no-hash) __SR_W stage path stays byte-identical (plain write, no marker, exit 0)')
  }

  fs.rmSync(tmpDir, { recursive: true, force: true })
  console.log('ok: #410 io.writeFile verifies every courier write — faithful writes land, refused/mutated/empty/prose fail loudly')
}

main().catch((e) => { console.error('FAIL:', e.message || e, e.stack); process.exit(1) })
