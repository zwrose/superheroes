// plugins/superheroes/lib/bundle_showrunner.js
// Emit a self-contained Workflow-tool script. Strategy: a tiny module registry. Each real spine
// module is wrapped in a factory (its own scope), and a __require shim resolves inter-module
// requires; ./io_seam.js resolves to the preamble's leaf-bash io (no fs/path/os in the sandbox).
const fs = require('fs')
const path = require('path')

const LIB = __dirname
// io_seam is intentionally absent: the preamble provides a leaf-bash io for it.
// #115: review_panel_shell.js now requires the panel twins in-process, so they bundle BEFORE it in
// dependency order (circuit_breaker -> loop_state -> loop_synthesis -> panel_tally).
// #115 Task 12: phase_step, recover, front_half added — showrunner.js now requires them in-process.
// #115 Task 15: build_progress added — build_phase.js now requires it in-process (FR-4a).
// #115 Task 16: ci_status + verify_gate added — back-half twins (ship CI + verify gate classify in-process).
// ci_status before review_panel_shell (shell requires verify_gate; showrunner.js requires ci_status).
// #115 increment B: worker_recovery + task_review added — build_phase.js now requires them in-process
// (the two SMART deciders are twins now, no leaf). They bundle BEFORE build_phase.js; task_review's
// deps (circuit_breaker + loop_state) are already first in the array, worker_recovery is pure.
// #38 Task 10: engine_pref + engine_dispatch — external-engine resolver + dispatch leaf (before
// build_phase.js/showrunner.js, which require them in-process).
// #170: lib_root.js first — it has no deps and is required by the compose modules (showrunner /
// build_phase / engine_dispatch / review_panel_shell / fenced_json) to resolve __SR_LIB at call time.
const MODULES = ['lib_root.js', 'cost_meter.js',
                 'circuit_breaker.js', 'loop_state.js', 'loop_synthesis.js', 'panel_tally.js',
                 'review_round_policy.js',
                 'ci_status.js', 'verify_gate.js',
                 'review_memory.js',
                 'review_panel_shell.js', 'courier_exec.js', 'pr_comment_scrub.js', 'test_pilot_deciders.js', 'test_pilot_phase.js', 'build_progress.js',
                 'worker_recovery.js', 'task_review.js', 'engine_pref.js', 'engine_dispatch.js', 'build_phase.js',
                 'model_tier.js', 'phase_step.js', 'recover.js', 'front_half.js', 'fenced_json.js', 'showrunner.js']

// Registry keys are the bare module name (no './' prefix, no '.js' suffix). `norm` MUST match the
// runtime `__require`'s key derivation exactly, or every lookup throws "unknown module".
function norm(id) { return String(id).replace('./', '').replace(/\.js$/, '') }
function factory(name, src) {
  // The module body is inlined VERBATIM inside a factory; its require()/module.exports resolve to the
  // factory params. No line stripping -> no orphaned exports, no collisions, no surviving inline require.
  return '__modules[' + JSON.stringify(norm(name)) + '] = function (module, exports, require) {\n' + src + '\n};\n'
}

const PREAMBLE = `export const meta = {
  name: 'superheroes-showrunner',
  description: 'Run the superheroes showrunner end-to-end for one approved work-item (full-run, native front-half).',
}
// The Workflow runtime provides agent()/parallel()/log() in scope; bind them onto globalThis so the
// inlined spine (which reads globals) sees them. agent is WRAPPED so EVERY leaf gets, centrally:
//  (1) model pinning — dumb pipes (exec/io) are UNCONDITIONALLY pinned to the cheapest model
//      (DEFAULT_TIERS.mechanical) regardless of __SR_LEAF_MODEL or any session default; genuine-LLM
//      (smart) leaves get __SR_LEAF_MODEL when set (throwaway/test runs), preserve explicit
//      opts.model otherwise, or fall back to Opus. No leaf inherits the session model.
//  (2) the current phase as its progress group — globalThis.__SR_PHASE, set by runPhases — so the
//      Workflow UI shows named phases instead of a flat undifferentiated list.
// Display label: turn a generic 'lib'/'io' leaf into the lib script (+ subcommand) or io op it runs,
// derived from the prompt (which carries the command). Done HERE (bundle-only) — not in the spine's
// cmdRunner — so the node smokes, which route canned responses by the logical 'lib' label, are unaffected.
function __leafLabel(p, fallback) {
  var m = p.match(/([\\w-]+\\.py)(?:\\s+([a-z][\\w-]*))?/)
  if (m) return m[2] ? m[1] + ' ' + m[2] : m[1]
  if (p.indexOf('cat > ') >= 0) return 'io:write'
  if (p.indexOf('mkdir -p') >= 0) return 'io:mkdir'
  if (p.indexOf('cat ') >= 0) return 'io:read'
  return fallback || 'lib'
}
// __cheapest: resolves the mechanical (cheapest) model tier once via the bundled model_tier module and
// caches it. Called lazily inside the wrapper (at agent-call time, after the module registry is set up).
var __cheapestCache = null
function __cheapest() {
  if (__cheapestCache === null) __cheapestCache = __require('model_tier').DEFAULT_TIERS.mechanical
  return __cheapestCache
}
// __safeSmartDefault: final fallback for any genuine leaf whose caller forgot opts.model. Resolving
// the synthesis tier through the bundled model_tier module gives the explicit Opus safety floor and
// keeps this lazy like __cheapest().
var __safeSmartDefaultCache = null
function __safeSmartDefault() {
  if (__safeSmartDefaultCache === null) __safeSmartDefaultCache = __require('model_tier').resolveModel('synthesis', null, null)
  return __safeSmartDefaultCache
}
function __payloadModel() {
  return __require('model_tier').resolveModel('fixer', globalThis.__SR_OVERRIDES || null, 'code') || __safeSmartDefault()
}
const __realAgent = agent
globalThis.agent = function (prompt, opts) {
  var o = Object.assign({}, opts || {})
  // Dumb-pipe detection. The AUTHORITATIVE marker is o.courier === true — every dumb pipe (the batch
  // exec() and the single-command courier) sets it, so cheapest-model pinning is decoupled from the
  // now-cosmetic display label (leaves carry descriptive purposes like 'read gate', 'prepare build').
  // The label checks are back-compat for older callers/bundles and cover the exec:*/io:* prefix shape;
  // exec and io leaves are pure side-effect executors — they ALWAYS run at the cheapest model
  // unconditionally, independent of __SR_LEAF_MODEL or any session default. Genuine-LLM (smart) leaves
  // get __SR_LEAF_MODEL when set (throwaway/test run override).
  var __lbl = (typeof o.label === 'string') ? o.label : ''
  var __payload = o.payload === true
  var __isDumb = (o.courier === true || __lbl === 'exec' || __lbl === 'io' ||
                  __lbl.indexOf('exec:') === 0 || __lbl.indexOf('io:') === 0)
  if (o.courier !== undefined) delete o.courier   // courier marker is preamble-only, never forwarded
  if (o.payload !== undefined) delete o.payload   // payload marker is preamble-only, never forwarded
  if (__isDumb && __payload) {
    o.model = __payloadModel()
  } else if (__isDumb) {
    o.model = __cheapest()
  } else if (globalThis.__SR_LEAF_MODEL) {
    o.model = globalThis.__SR_LEAF_MODEL
  }
  if (!o.model) o.model = __safeSmartDefault()
  if (!o.phase && globalThis.__SR_PHASE) o.phase = globalThis.__SR_PHASE
  if (!o.label || o.label === 'lib' || o.label === 'io') o.label = __leafLabel(String(prompt), o.label)
  // #130 token telemetry: count this dispatch under the current phase, keyed by the resolved model
  // (the proxy backbone). This is the single dispatch choke-point. Best-effort — never break a
  // dispatch for telemetry. The phase's own persist leaf is excluded by ordering (cost_meter.take
  // resets the phase before that leaf dispatches), not by any flag.
  try { __require('cost_meter').record(o.model) } catch (_) {}
  return __realAgent(prompt, o)
}
globalThis.parallel = parallel
globalThis.log = (typeof log === 'function') ? log : (() => {})
// #130: expose the Workflow budget to the spine (runPhases reads budget.spent() at phase boundaries
// via cost_meter). Absent outside the Workflow runtime -> null -> tokens stay unmeasured (proxy only).
globalThis.__SR_BUDGET = (typeof budget !== 'undefined') ? budget : null
// Leaf-bash io: every filesystem touch runs in a command-runner leaf, so the script body needs no fs.
// __sh dispatches through globalThis.agent (the wrapper) so io leaves also get the model/phase enrichment.
function __q(s) { return "'" + String(s).replace(/'/g, "'\\\\''") + "'" }
function __sc(cmd) {
  var root = (typeof globalThis !== 'undefined' && globalThis.__SR_ROOT) ? String(globalThis.__SR_ROOT) : null
  if (!root) return cmd
  var t = String(cmd).replace(/^\\s+/, '')
  if (t.startsWith('cd ')) return cmd
  return 'cd ' + __q(root) + ' && ' + cmd
}
async function __sh(cmd, opts) {
  return globalThis.agent(
    'Execute this exact shell command via your command tool and return ONLY its stdout, unchanged. Do not echo, fence, summarize, or describe the command:\\n\\n' + __sc(cmd),
    Object.assign({ label: 'io', courier: true }, opts || {}),
  )
}
function __join() { return Array.prototype.slice.call(arguments).join('/').replace(/\\/+/g, '/') }
// __contentHash: sha-256 over the string's UTF-8 BYTES, hex — byte-identical to Python's
// hashlib.sha256(text.encode('utf-8')).hexdigest() and io_seam's crypto twin. Parity is
// load-bearing: the fenced set-gate compares this against definition_doc.content_hash, so a
// divergence parks every live gate write as 'stale'. Byte-array padding (no string escapes),
// so no control characters appear in this script (the Workflow permission layer rejects them).
// Lone surrogates encode as U+FFFD, matching node's utf-8 conversion.
function __utf8Bytes(text) {
  var str = String(text || ''), bytes = [], i, c
  for (i = 0; i < str.length; i++) {
    c = str.charCodeAt(i)
    if (c < 0x80) bytes.push(c)
    else if (c < 0x800) bytes.push(0xc0 | (c >> 6), 0x80 | (c & 63))
    else if (c >= 0xd800 && c < 0xdc00 && i + 1 < str.length && str.charCodeAt(i + 1) >= 0xdc00 && str.charCodeAt(i + 1) < 0xe000) {
      c = 0x10000 + ((c - 0xd800) << 10) + (str.charCodeAt(i + 1) - 0xdc00); i++
      bytes.push(0xf0 | (c >> 18), 0x80 | ((c >> 12) & 63), 0x80 | ((c >> 6) & 63), 0x80 | (c & 63))
    } else if (c >= 0xd800 && c < 0xe000) bytes.push(0xef, 0xbf, 0xbd)
    else bytes.push(0xe0 | (c >> 12), 0x80 | ((c >> 6) & 63), 0x80 | (c & 63))
  }
  return bytes
}
// __b64: base64 over the UTF-8 bytes — the OPAQUE payload encoding for writeFile (an LLM leaf
// can copy an alphabet-soup blob verbatim or fail visibly; it cannot paraphrase it the way it
// can rewrite readable JSON — the live 2026-07-02 staged-write mangle class).
function __b64(text) {
  var bytes = __utf8Bytes(text), A = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/', out = ''
  for (var i = 0; i < bytes.length; i += 3) {
    var b0 = bytes[i], b1 = bytes[i + 1], b2 = bytes[i + 2]
    out += A[b0 >> 2] + A[((b0 & 3) << 4) | ((b1 === undefined ? 0 : b1) >> 4)]
    out += (b1 === undefined) ? '=' : A[((b1 & 15) << 2) | ((b2 === undefined ? 0 : b2) >> 6)]
    out += (b2 === undefined) ? '=' : A[b2 & 63]
  }
  return out
}
function __contentHash(text) {
  var bytes = __utf8Bytes(text), i, j
  var hi = (bytes.length / 0x20000000) | 0, lo = (bytes.length << 3) >>> 0
  bytes.push(0x80)
  while (bytes.length % 64 !== 56) bytes.push(0)
  bytes.push((hi >>> 24) & 255, (hi >>> 16) & 255, (hi >>> 8) & 255, hi & 255,
             (lo >>> 24) & 255, (lo >>> 16) & 255, (lo >>> 8) & 255, lo & 255)
  var H = [0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19]
  var K = [0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da, 0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070, 0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2]
  var w = new Array(64)
  for (i = 0; i < bytes.length; i += 64) {
    for (j = 0; j < 16; j++) {
      var o = i + j * 4
      w[j] = (bytes[o] << 24) | (bytes[o + 1] << 16) | (bytes[o + 2] << 8) | bytes[o + 3]
    }
    for (j = 16; j < 64; j++) {
      var x = w[j - 15], y = w[j - 2]
      var s0 = ((x >>> 7) | (x << 25)) ^ ((x >>> 18) | (x << 14)) ^ (x >>> 3)
      var s1 = ((y >>> 17) | (y << 15)) ^ ((y >>> 19) | (y << 13)) ^ (y >>> 10)
      w[j] = (w[j - 16] + s0 + w[j - 7] + s1) | 0
    }
    var a = H[0], b = H[1], c2 = H[2], d = H[3], e = H[4], f = H[5], g = H[6], h = H[7]
    for (j = 0; j < 64; j++) {
      var S1 = ((e >>> 6) | (e << 26)) ^ ((e >>> 11) | (e << 21)) ^ ((e >>> 25) | (e << 7))
      var t1 = (h + S1 + ((e & f) ^ (~e & g)) + K[j] + w[j]) | 0
      var S0 = ((a >>> 2) | (a << 30)) ^ ((a >>> 13) | (a << 19)) ^ ((a >>> 22) | (a << 10))
      var t2 = (S0 + ((a & b) ^ (a & c2) ^ (b & c2))) | 0
      h = g; g = f; f = e; e = (d + t1) | 0; d = c2; c2 = b; b = a; a = (t1 + t2) | 0
    }
    H[0] = (H[0] + a) | 0; H[1] = (H[1] + b) | 0; H[2] = (H[2] + c2) | 0; H[3] = (H[3] + d) | 0
    H[4] = (H[4] + e) | 0; H[5] = (H[5] + f) | 0; H[6] = (H[6] + g) | 0; H[7] = (H[7] + h) | 0
  }
  var out = ''
  for (i = 0; i < 8; i++) for (j = 3; j >= 0; j--) out += ('0' + ((H[i] >>> (j * 8)) & 255).toString(16)).slice(-2)
  return out
}
// __helperResult: parse a leaf-bash helper answer (stdout + trailing __SR_EXIT:N marker) into the
// runHelper result shape. Shared by runHelper and stageAndRunHelper (fold 1, #141) so both keep the
// SAME fence tolerance + exit-marker slice. Find the LAST marker anywhere (a misbehaving haiku
// courier stochastically fences the answer AFTER the marker), slice stdout up to it, strip one
// wrapping fence pair.
function __helperResult(s) {
  s = String(s || '')
  var re = /__SR_EXIT:(\\d+)/g, m, last = null
  while ((m = re.exec(s)) !== null) last = m
  var status = last ? Number(last[1]) : 1
  var stdout = last ? s.slice(0, last.index) : s
  var markerTail = last ? s.slice(last.index + last[0].length) : ''
  stdout = stdout.replace(/^\\s*\`\`\`[a-zA-Z0-9]*\\n?/, '').replace(/\\n?\`\`\`\\s*$/, '').replace(/\\n$/, '')
  if (/^\\s*\\x60/.test(stdout) && (/\\x60\\s*$/.test(stdout) || /^\\s*\\x60\\s*$/.test(markerTail))) {
    stdout = stdout.replace(/^\\s*\\x60/, '').replace(/\\x60\\s*$/, '')
  }
  return { ok: status === 0, status: status, stdout: stdout, stderr: '' }
}
const __PAYLOAD_BOUND = 3000
const __PAYLOAD_CHARS = 1200
const __NL = String.fromCharCode(10)
function __libPath(name) {
  return __require('lib_root').libPath(name)
}
function __argv(cmd, args) { return [cmd].concat(args || []).map(function (a) { return __q(String(a)) }).join(' ') }
function __textChunks(text, size) {
  var chunks = []
  for (var i = 0; i < text.length;) {
    var end = Math.min(text.length, i + size)
    var last = text.charCodeAt(end - 1)
    if (end < text.length && last >= 0xd800 && last < 0xdc00) end -= 1
    if (end <= i) end = Math.min(text.length, i + size)
    chunks.push(text.slice(i, end)); i = end
  }
  if (!chunks.length) chunks.push('')
  return chunks
}
async function __runHelperCommand(args, payload) {
  var parts = __argv('python3', args)
  return __helperResult(String(await __sh(parts + ' 2>&1; echo __SR_EXIT:$?', payload ? { payload: true } : {}) || ''))
}
async function __stageChunkFile(stagedPath, index, total, chunkText) {
  var b64 = __b64(chunkText)
  var args = [__libPath('review_memory.py'), 'stage-chunk', '--path', stagedPath,
              '--index', String(index), '--total', String(total),
              '--chunk-b64', b64, '--chunk-hash', __contentHash(b64)]
  for (var attempt = 0; attempt < 2; attempt++) {
    var out = await __runHelperCommand(args, true)
    try { var parsed = JSON.parse(out.stdout || '') } catch (_) { parsed = null }
    if (parsed && parsed.ok) return
  }
  throw new Error('payload-stage-failed')
}
async function __chunkedStageAndRun(stagedPath, text, cmd, args) {
  var chunks = __textChunks(text, __PAYLOAD_CHARS)
  for (var i = 0; i < chunks.length; i++) await __stageChunkFile(stagedPath, i, chunks.length, chunks[i])
  var finish = __argv('python3', [__libPath('review_memory.py'), 'finish-chunks', '--path', stagedPath,
                                 '--total', String(chunks.length), '--payload-hash', __contentHash(text)])
  var helper = __argv(cmd, args || [])
  var chain = finish + ' >/dev/null && ' + helper + ' 2>&1; echo __SR_EXIT:$?'
  return __helperResult(String(await __sh(chain, { payload: true }) || ''))
}
globalThis.io = {
  join: __join, tmpdir() { return '/tmp' },
  async mkdirp(d) { await __sh('mkdir -p ' + __q(d)) },
  // writeFile rides an OPAQUE transport: the payload travels base64-encoded inside a python
  // heredoc and is decoded + written byte-exact Python-side. An LLM leaf can only copy the
  // blob verbatim or fail visibly — it cannot paraphrase the content the way it can rewrite
  // readable JSON (live 2026-07-02: a staged dim-write leaf re-wrote the PREVIOUS dimension's
  // content). Byte-exact also means no heredoc trailing-newline artifact on new writes (the
  // Python-side staged-hash checks keep the one-newline tolerance for old-bundle compat).
  async writeFile(p, s) {
    const b = (typeof s === 'string') ? s : JSON.stringify(s)
    const encoded = __b64(b)
    const script = "python3 - <<'__SR_EOF__'" + __NL +
      "import base64" + __NL +
      "with open(" + JSON.stringify(p) + ", 'wb') as fh:" + __NL +
      "    fh.write(base64.b64decode('" + encoded + "'))" + __NL +
      "print('ok')" + __NL +
      "__SR_EOF__"
    await __sh(script, encoded.length > __PAYLOAD_BOUND ? { payload: true } : {})
  },
  // stageAndRunHelper: fold 1 (#141) — the single-leaf twin of writeFile(stagedPath)+runHelper. ONE
  // command chains: mkdir -p <parent> && <opaque base64 stage-write, stdout to /dev/null> && <helper>.
  // The stage rides the SAME opaque base64 heredoc transport as writeFile (an LLM leaf copies the blob
  // verbatim or fails visibly), and its stdout is suppressed so ONLY the helper's answer precedes the
  // exit marker. A mangled/failed stage short-circuits the && so the helper never runs — the caller's
  // Python-side --payload-hash check then fails closed exactly as before, one retry. D3 byte-identical.
  async stageAndRunHelper(stagedPath, text, cmd, args) {
    const b = (typeof text === 'string') ? text : JSON.stringify(text)
    if (__b64(b).length > __PAYLOAD_BOUND) return __chunkedStageAndRun(stagedPath, b, cmd, args)
    var dir = String(stagedPath).slice(0, String(stagedPath).lastIndexOf('/'))
    var mk = dir ? ('mkdir -p ' + __q(dir) + ' && ') : ''
    var helper = __argv(cmd, args || [])
    var chain = mk + "python3 - <<'__SR_EOF__' >/dev/null && " + helper + ' 2>&1; echo __SR_EXIT:$?' + __NL +
      'import base64' + __NL +
      'with open(' + JSON.stringify(stagedPath) + ", 'wb') as fh:" + __NL +
      "    fh.write(base64.b64decode('" + __b64(b) + "'))" + __NL +
      '__SR_EOF__'
    return __helperResult(String(await __sh(chain) || ''))
  },
  async readText(p) { return __sh('cat ' + __q(p) + ' 2>/dev/null || true') },
  async readJson(p, dflt) { const t = await __sh('cat ' + __q(p) + ' 2>/dev/null || true'); try { return JSON.parse(t) } catch (_) { return dflt } },
  contentHash(text) { return __contentHash(text) },
  async runHelper(cmd, args) {
    var parts = __argv(cmd, args || [])
    // A misbehaving haiku courier STOCHASTICALLY wraps the whole answer in \`\`\` fences (live
    // 2026-07-02: 3 of 4 runHelper leaves fenced), pushing the fence AFTER the exit marker so an
    // end-anchored match misses and a clean exit-0 helper is falsely read as FAILED (coverage-
    // decisions-unreadable / telemetry-write-failed / memory degraded — the review-plan park class).
    // __helperResult finds the LAST marker anywhere, slices stdout up to it, strips one wrapping
    // fence pair. Mirrors extractJson's fence tolerance; runCourierText stays non-stripping (its
    // payload is arbitrary text that may legitimately contain fences).
    return __helperResult(String(await __sh(parts + ' 2>&1; echo __SR_EXIT:$?') || ''))
  },
}
// Full-run mode (read by showrunner() in Task 8): inject native authoring WITHOUT frontHalfBoundary.
globalThis.SUPERHEROES_BUNDLE_FULL_RUN = true

const __modules = {}
const __cache = {}
function __require(id) {
  const key = String(id).replace('./', '').replace(/\\.js$/, '')   // MUST match the bundler's norm()
  // io_seam is supplied by the preamble (leaf-bash) — never the fs-backed disk module.
  if (key === 'io_seam') return { io: function () { return globalThis.io }, joinPath: __join }
  if (__cache[key]) return __cache[key].exports
  if (!__modules[key]) throw new Error('bundle: unknown module ' + id)
  const m = { exports: {} }
  __cache[key] = m
  __modules[key](m, m.exports, __require)
  return m.exports
}
globalThis.__sr_require = __require   // exposed so the compose smoke can resolve the registry
`

// The Workflow runtime runs this script in an async context and awaits the script
// body's top-level promise. The entry must therefore `return` the showrunner promise
// at the top level (NOT fire-and-forget it inside an un-awaited IIFE) — a floating
// promise is never awaited, so the run would tear down before any agent() executes
// (0 agents, instant exit). Top-level `return` is valid in the runtime's async wrapper;
// the bundle smoke evaluates the script inside an async wrapper too, so it parses there.
const ENTRY = `
if (globalThis.__SR_RUN !== false) {
  // The Workflow runtime delivers the tool's args input as a JSON STRING (not a parsed object), so
  // accept either: parse a string, pass an object through. A non-JSON / missing value -> clear throw.
  let __a = args
  if (typeof __a === 'string') { try { __a = JSON.parse(__a) } catch (_) { __a = null } }
  const wi = (__a && typeof __a === 'object') ? __a.workItem : null
  if (!wi) throw new Error('showrunner bundle requires args.workItem')
  // Optional cheap-leaf override for throwaway/test runs (args.model, e.g. 'haiku'); absent in
  // production so the per-role model tiers govern. The preamble's agent wrapper applies it.
  if (__a && __a.model) globalThis.__SR_LEAF_MODEL = __a.model
  // FR-5: thread the explicit repo root so leaf commands cd to the correct checkout regardless of
  // the haiku leaf's cwd. Callers pass args.root = <abs repo root> to opt in; absent in production
  // (where the leaf cwd is the correct repo) the guard is unset and selfContained() is a no-op.
  if (__a && __a.root) globalThis.__SR_ROOT = __a.root
  // #170: thread the spine CODE root — where every python3 <lib>/<cli>.py compose points, DISTINCT
  // from __SR_ROOT (the target repo git/build/docs operate on). The launching skill passes an
  // absolute plugin-cache lib dir (CLAUDE_PLUGIN_ROOT + /lib — immutable + versioned) so the run is
  // pinned to its launch-time code version and portable to any repo. The relative default IS the
  // pre-#170 behavior (resolves under the leaf's cd <root>), so a no-args / no-libRoot launch stays
  // byte-identical. lib_root.js reads this at call time.
  globalThis.__SR_LIB = (__a && typeof __a.libRoot === 'string' && __a.libRoot) ? __a.libRoot : 'plugins/superheroes/lib'
  // args-based front-half selector (Task 13a, #115): args.frontHalf==='native' opts into a
  // front-half-only run (parks at the workhorse boundary). This drives the sandbox selector
  // because the env path (SUPERHEROES_FRONT_HALF) is unavailable in the Workflow sandbox (FR-8).
  // The preamble sets SUPERHEROES_BUNDLE_FULL_RUN=true as the safe default; the ENTRY's
  // assignment here runs AFTER the preamble so it correctly overrides that default.
  const frontHalfNative = !!(__a && __a.frontHalf === 'native')
  globalThis.SUPERHEROES_FRONT_HALF_NATIVE = frontHalfNative
  globalThis.SUPERHEROES_BUNDLE_FULL_RUN = !frontHalfNative
  // Configurable base branch (#115): args.base is the branch name to build off of and PR into.
  // Absent -> unset (each site falls back to its default: _base() / 'main' / gh default).
  if (__a && __a.base) globalThis.__SR_BASE = __a.base
  // #25 quick discovery: args.route is the discovery-declared route ('quick' | 'full'). It is
  // HONORED when it agrees with the on-disk artifact and REFUSED (fail-closed) when it conflicts —
  // never silently overridden in either direction (resolveIntake). Absent ⇒ unset ⇒ the spine derives
  // the route from the artifact alone (spec ⇒ full, tasks ⇒ quick; byte-identical to pre-#25). PR 2
  // (the-architect leg) passes it on a quick launch.
  if (__a && __a.route) globalThis.__SR_ROUTE = __a.route
  return __require('showrunner.js').showrunner({ workItem: wi })
}
`

function emit() {
  const factories = MODULES.map((f) => '// ===== ' + f + ' =====\n' + factory(f, fs.readFileSync(path.join(LIB, f), 'utf8')))
  const out = PREAMBLE + '\n' + factories.join('\n') + '\n' + ENTRY
  // The Workflow tool's permission layer rejects scripts containing raw control characters, so a
  // bundle carrying one can never be launched verbatim. Refuse to emit it — escape the offending
  // literal (\xNN) in the source module instead. Tab/newline are the only allowed controls.
  const raw = out.match(/[\u0000-\u0008\u000b-\u001f\u007f-\u009f]/)
  if (raw) {
    throw new Error('bundle would contain a raw control byte 0x' +
      raw[0].charCodeAt(0).toString(16) + ' at index ' + raw.index +
      ' — escape it (\\xNN) in the source module')
  }
  return out
}

function main(argv) {
  const out = path.join(LIB, 'showrunner.bundle.js')
  if (argv.includes('--check')) {
    const fresh = emit()
    const committed = fs.existsSync(out) ? fs.readFileSync(out, 'utf8') : ''
    if (fresh !== committed) { process.stderr.write('bundle drift: regenerate with `node bundle_showrunner.js --write`\n'); process.exit(1) }
    process.stdout.write('bundle up to date\n'); return
  }
  if (argv.includes('--write')) { fs.writeFileSync(out, emit()); process.stdout.write('wrote ' + out + '\n'); return }
  process.stdout.write(emit())
}
main(process.argv.slice(2))
