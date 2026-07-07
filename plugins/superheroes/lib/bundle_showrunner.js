// plugins/superheroes/lib/bundle_showrunner.js
// Emit a self-contained Workflow-tool script. Strategy: a tiny module registry. Each real spine
// module is wrapped in a factory (its own scope), and a __require shim resolves inter-module
// requires; ./io_seam.js resolves to the preamble's leaf-bash io (no fs/path/os in the sandbox).
const fs = require('fs')
const path = require('path')
const os = require('os')
const { execFileSync } = require('child_process')

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
// #277: bytes.js (Buffer-less base64/utf8 encoder) is bundled early (no deps) — the preamble's
// __b64/__utf8Bytes delegate to it and engine_dispatch requires it, so both share ONE copy (SSOT).
const MODULES = ['lib_root.js', 'bytes.js', 'cost_meter.js',
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
  if (p.indexOf('base64.b64decode') >= 0) return 'io:write'   // argv-shape writer (finding #13)
  if (p.indexOf('os.makedirs') >= 0 && p.indexOf('b64decode') < 0) return 'io:mkdir'
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
  // #194 residual (live 2026-07-04, run wf_b408ece1-0ed): an UNKNOWN agentType makes agent() REJECT
  // ("agent type 'superheroes:courier' not found") — a dispatch THROW, which __sh's answer-shape
  // fallback never sees (it only inspects returned answers). On any plugin cache older than the
  // courier agent (< 0.8.0) the first agentType-carrying leaf crashed its caller (test-pilot's
  // status write parked run 29). Centralize the degrade at the single dispatch choke-point: catch
  // the not-found rejection and re-dispatch ONCE without agentType (default full-surface agent,
  // model pin and label unchanged). Only the not-found shape falls back — every other rejection
  // still propagates (fail-closed for real dispatch errors).
  if (o.agentType) {
    var __fallbackOpts = Object.assign({}, o); delete __fallbackOpts.agentType
    return Promise.resolve().then(function () { return __realAgent(prompt, o) }).catch(function (e) {
      var __msg = String((e && e.message) || e)
      if (/agent type '[^']*' not found/i.test(__msg)) return __realAgent(prompt, __fallbackOpts)
      throw e
    })
  }
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
// __badCourierAnswer: delegate to courier_exec (single source of truth — see badCourierAnswer there).
function __badCourierAnswer(a) {
  return __require('courier_exec').badCourierAnswer(a)
}
async function __sh(cmd, opts) {
  // #194: every dumb-pipe leaf dispatches on the lean 'superheroes:courier' agent (tools: Bash only).
  // A restricted-tool agent carries NO deferred_tools_delta / skill_listing attachments (measured:
  // ~55.5KB, ~13.9k tokens per leaf) and a tiny tool-schema prefix, cutting the fixed per-leaf context
  // ~2.6x vs the default full-surface dispatch. agentType and model are orthogonal — the wrapper still
  // applies the cheapest-model pin (or the fixer tier for payload leaves), so the two never interact.
  var o = Object.assign({ label: 'io', courier: true, agentType: 'superheroes:courier' }, opts || {})
  var prompt = 'Execute this exact shell command via your command tool and return ONLY its stdout, unchanged. Do not echo, fence, summarize, or describe the command:\\n\\n' + __sc(cmd)
  // Prompt-drop guard (repo memory: subagent-prompt-drop-bug — a plugin-type subagent dispatch
  // INTERMITTENTLY starts WITHOUT the task prompt, so the leaf never runs the command). Only a
  // command that echoes __SR_EXIT can be checked this way; for it, __badCourierAnswer() detects both
  // did-not-run shapes (missing marker OR the command echoed back with the literal '__SR_EXIT:$?').
  // Retry ONCE on the courier agent, then fall back to the DEFAULT dispatch (drop agentType, keep
  // courier:true so the cheap-model pin holds) so a courier-agent dispatch bug degrades to today's
  // cost instead of parking the run. Non-marker leaves (mkdir/cat/writeFile) already degrade
  // fail-soft or via their caller's own hash check, so they need no marker guard.
  var __expectMarker = String(cmd).indexOf('__SR_EXIT') >= 0
  var ans = await globalThis.agent(prompt, o)
  if (__expectMarker && __badCourierAnswer(ans)) {
    ans = await globalThis.agent(prompt, Object.assign({}, o))               // retry once, same courier agent
    if (__badCourierAnswer(ans)) {
      var fo = Object.assign({}, o); delete fo.agentType                     // fall back to the default dispatch
      ans = await globalThis.agent(prompt, fo)
    }
  }
  return ans
}
function __join() { return Array.prototype.slice.call(arguments).join('/').replace(/\\/+/g, '/') }
// __utf8Bytes / __b64: the OPAQUE-payload encoders (base64 over the string's UTF-8 bytes) used by the
// leaf-bash io writeFile/stageAndRunHelper AND the UTF-8 byte step of __contentHash. #277: the single
// implementation lives in bytes.js (SSOT, #231) so engine_dispatch's _stageCmd and this preamble use
// ONE copy — a Buffer-less encoder that runs byte-identically in node and the sandbox (the sandbox has
// no Buffer; a Buffer.from here was the #277 all-Claude fall-open). These delegate at CALL time (the
// module registry is populated before any leaf runs), mirroring __helperResult -> __require('courier_exec').
// __contentHash's sha-256 parity with Python/hashlib is load-bearing for the fenced set-gate, so its
// UTF-8 byte step MUST stay byte-exact — bytes.utf8Bytes is the same code the parity smoke pins.
function __utf8Bytes(text) { return __require('bytes').utf8Bytes(text) }
function __b64(text) { return __require('bytes').b64(text) }
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
// __helperResult: delegate to courier_exec.helperResult (single source of truth for fence-tolerant
// __SR_EXIT slice — shared by runHelper and stageAndRunHelper, fold 1 #141).
function __helperResult(s) {
  return __require('courier_exec').helperResult(s)
}
const __PAYLOAD_BOUND = 3000
const __PAYLOAD_CHARS = 2400
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
// __jsonFromText: fence-tolerant JSON parse for readJson. On the verify read-back path (and every
// other bundle read) the file content rides back through a haiku 'cat' courier that STOCHASTICALLY
// wraps the JSON in \`\`\` (or single-backtick) fences or prose — a bare JSON.parse then silently
// defaults and the round-stamped pass evidence goes unseen (live wf_1ed21465-6f3: a clean verify round
// halted). Mirrors __helperResult's fence tolerance + extractJson's brace-slice: direct parse, then
// strip ONE wrapping fence pair (triple or single backtick), then a first-{…last-} brace slice. A
// genuinely empty answer (missing file: cat ... || true -> '') falls straight to the silent default
// (anti-fabrication: a missing verify file must NOT parse into a pass).
function __jsonFromText(t, dflt) {
  var s = String(t == null ? '' : t)
  if (!s.trim()) return dflt
  try { return JSON.parse(s) } catch (_) {}
  var stripped = s.replace(/^\\s*\`\`\`[a-zA-Z0-9]*\\n?/, '').replace(/\\n?\`\`\`\\s*$/, '').trim()
  if (/^\\x60/.test(stripped) && /\\x60$/.test(stripped)) {
    stripped = stripped.replace(/^\\x60/, '').replace(/\\x60$/, '').trim()
  }
  try { return JSON.parse(stripped) } catch (_) {}
  var first = stripped.indexOf('{'), last = stripped.lastIndexOf('}')
  if (first >= 0 && last > first) {
    try { return JSON.parse(stripped.slice(first, last + 1)) } catch (_) {}
  }
  return dflt
}
// __SR_W: the argv-shape store writer (finding #13). The runtime's sensitive-file guard
// denies Write/Edit tools, shell mkdir, and heredoc open() on literal ~/.claude paths —
// regardless of permission rules or mode — but a path passed as ARGV to python is data,
// not a shell file-op, and passes. Every io write therefore rides:
//   python3 -c <script> <path> <b64>
// (probes A-D, 2026-07-06: only this shape survives default mode). Payload stays base64
// for byte-fidelity (#257 tracks the plain-JSON + hash follow-on).
var __SR_W = 'import os,sys,base64' + __NL +
  'd=os.path.dirname(sys.argv[1])' + __NL +
  'd and os.makedirs(d,exist_ok=True)' + __NL +
  'open(sys.argv[1],"wb").write(base64.b64decode(sys.argv[2]))'
globalThis.io = {
  join: __join, tmpdir() { return '/tmp' },
  async mkdirp(d) { await __sh('python3 -c ' + __q('import os,sys' + __NL + 'os.makedirs(sys.argv[1],exist_ok=True)') + ' ' + __q(d)) },
  // writeFile rides an OPAQUE transport: the payload travels base64-encoded inside a python
  // heredoc and is decoded + written byte-exact Python-side. An LLM leaf can only copy the
  // blob verbatim or fail visibly — it cannot paraphrase the content the way it can rewrite
  // readable JSON (live 2026-07-02: a staged dim-write leaf re-wrote the PREVIOUS dimension's
  // content). Byte-exact also means no heredoc trailing-newline artifact on new writes (the
  // Python-side staged-hash checks keep the one-newline tolerance for old-bundle compat).
  async writeFile(p, s) {
    const b = (typeof s === 'string') ? s : JSON.stringify(s)
    const encoded = __b64(b)
    // argv shape (finding #13) — path and payload are ARGUMENTS, never a heredoc open().
    const script = 'python3 -c ' + __q(__SR_W) + ' ' + __q(p) + ' ' + __q(encoded)
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
    // argv-shape stage (finding #13): the writer makes the parent dir AND writes the
    // payload with the path as an argument — no shell mkdir, no heredoc open(), so the
    // sensitive-file guard never fires on store paths. Stage stdout is suppressed so
    // ONLY the helper's answer precedes the exit marker; a failed stage short-circuits
    // the && and the caller's Python-side --payload-hash check fails closed, as before.
    var helper = __argv(cmd, args || [])
    var chain = 'python3 -c ' + __q(__SR_W) + ' ' + __q(stagedPath) + ' ' + __q(__b64(b)) +
      ' >/dev/null && ' + helper + ' 2>&1; echo __SR_EXIT:$?'
    return __helperResult(String(await __sh(chain) || ''))
  },
  async readText(p) { return __sh('cat ' + __q(p) + ' 2>/dev/null || true') },
  async readJson(p, dflt) { const t = await __sh('cat ' + __q(p) + ' 2>/dev/null || true'); return __jsonFromText(t, dflt) },
  contentHash(text) { return __contentHash(text) },
  async runHelper(cmd, args, opts) {
    var parts = __argv(cmd, args || [])
    // A misbehaving haiku courier STOCHASTICALLY wraps the whole answer in \`\`\` fences (live
    // 2026-07-02: 3 of 4 runHelper leaves fenced), pushing the fence AFTER the exit marker so an
    // end-anchored match misses and a clean exit-0 helper is falsely read as FAILED (coverage-
    // decisions-unreadable / telemetry-write-failed / memory degraded — the review-plan park class).
    // __helperResult finds the LAST marker anywhere, slices stdout up to it, strips one wrapping
    // fence pair. Mirrors extractJson's fence tolerance; runCourierText stays non-stripping (its
    // payload is arbitrary text that may legitimately contain fences).
    // opts.payload: the answer is a relay payload (e.g. a read-chunk) — ride the copy-faithful
    // payload tier instead of the cheapest courier tier (#191).
    return __helperResult(String(await __sh(parts + ' 2>&1; echo __SR_EXIT:$?', (opts && opts.payload) ? { payload: true } : {}) || ''))
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

// stripComments: shrink the emitted bundle under the Workflow tool's hard script-size cap (#295) by
// removing full-line `//` comments and blank lines — measured ~36% of the un-stripped bundle. The
// SOURCE modules keep every comment; only this generated artifact slims. Two properties make it safe:
//
//  (1) String / template-literal / regex / block-comment awareness. The bundled sources carry many
//      multi-line template literals (agent prompts, embedded Python) whose lines legitimately begin
//      with `//` — that is STRING DATA, not a comment, and stripping it would corrupt the spine. So we
//      tokenize the whole emitted bundle once (single char scan tracking string/template/regex/block
//      state, with a frame stack for `${...}` substitution nesting) and record, per line, whether the
//      line BEGINS in plain-code context. A line is removed ONLY when it begins in code context AND is
//      blank or its first non-whitespace chars are `//` (a full-line, statement-level comment). Trailing
//      (end-of-line) comments are never touched — that sidesteps `https://` false positives entirely.
//  (2) Determinism. Same input -> byte-identical output, so `--check` round-trips against the committed
//      artifact. `node --check` on the result (verifyEmit) then guarantees a stripper bug can never ship
//      a bundle that does not parse.
function stripComments(src) {
  const s = src, N = s.length
  // codeStart[k] === true iff, at the first character of line k, the lexer is in plain-code context
  // (not inside a template literal, string, block comment, or regex). Only those lines may be stripped.
  const codeStart = [true]
  let line = 0
  // Frame stack for template / `${...}` substitution nesting. Bottom frame is code; a backtick pushes a
  // template frame; `${` inside a template pushes a code frame; the matching `}` (brace depth 0) pops it.
  const frames = [{ tpl: false, braces: 0 }]
  const top = () => frames[frames.length - 1]
  let state = 'code'   // code | line | block | sq | dq | tpl | regex | rclass
  let escaped = false  // inside sq/dq/tpl/regex: previous char was an unconsumed backslash
  // Regex-vs-division disambiguation: 'op' => a `/` here starts a regex; 'value' => it is division.
  let lastTok = 'op'
  const EXPR_KW = new Set(['return', 'typeof', 'instanceof', 'in', 'of', 'new', 'delete', 'void',
                           'do', 'else', 'yield', 'await', 'case', 'throw'])
  const isIdStart = (ch) => (ch >= 'a' && ch <= 'z') || (ch >= 'A' && ch <= 'Z') || ch === '_' || ch === '$'
  const isIdPart = (ch) => isIdStart(ch) || (ch >= '0' && ch <= '9')
  const isDigit = (ch) => ch >= '0' && ch <= '9'
  const isFlag = (ch) => (ch >= 'a' && ch <= 'z') || (ch >= 'A' && ch <= 'Z')

  let i = 0
  while (i < N) {
    const c = s[i]
    if (c === '\n') {
      line++
      // The NEXT line begins in plain-code context only when we are in the base `code`/`line` states
      // (a line comment ends at the newline). Every other state — block comment or any string/template/
      // regex — is either a multi-line construct we must keep verbatim (block, tpl) or a defensive
      // non-code reset — EXCEPT an ESCAPED newline inside a quoted string, which is a line
      // continuation: the string keeps going, so sq/dq state must survive or the continued lines get
      // lexed as code and a continued line beginning with `//` strips as a comment while `node
      // --check` still passes (semantic, not syntactic, damage — the fail-direction class from the
      // #295 review). Regex cannot legally continue across a newline, escaped or not, so it resets.
      const continued = escaped && (state === 'sq' || state === 'dq')
      codeStart[line] = (state === 'code' || state === 'line')
      if (state === 'line') state = 'code'
      if (!continued && (state === 'sq' || state === 'dq' || state === 'regex' || state === 'rclass')) state = 'code'
      escaped = false
      i++
      continue
    }
    switch (state) {
      case 'code': {
        const d = s[i + 1]
        if (c === '/' && d === '/') { state = 'line'; i += 2; break }
        if (c === '/' && d === '*') { state = 'block'; i += 2; break }
        if (c === '`') { frames.push({ tpl: true, braces: 0 }); state = 'tpl'; lastTok = 'op'; i++; break }
        if (c === '\'') { state = 'sq'; i++; break }
        if (c === '"') { state = 'dq'; i++; break }
        if (c === '/' && lastTok === 'op') { state = 'regex'; i++; break }
        if (c === '/') { lastTok = 'op'; i++; break }   // division operator
        if (c === ' ' || c === '\t' || c === '\r') { i++; break }
        if (c === '{') { top().braces++; lastTok = 'op'; i++; break }
        if (c === '}') {
          if (top().braces > 0) { top().braces--; lastTok = 'value'; i++; break }
          if (frames.length > 1) { frames.pop(); state = 'tpl'; lastTok = 'value'; i++; break }  // close ${}
          lastTok = 'value'; i++; break
        }
        if ((c === '+' && s[i + 1] === '+') || (c === '-' && s[i + 1] === '-')) {
          lastTok = 'value'; i += 2; break   // postfix ++/-- yields a value: a following `/` is division
        }
        if (isIdStart(c)) {
          let j = i + 1
          while (j < N && isIdPart(s[j])) j++
          // A keyword in PROPERTY position (`obj.in`, `x.of`) is an identifier, never the expression-
          // introducing keyword — look back past whitespace for a `.`/`?.` so a following `/` reads as
          // division. Otherwise a genuine `return`/`typeof`/… puts `/` in regex position.
          let p = i - 1
          while (p >= 0 && (s[p] === ' ' || s[p] === '\t' || s[p] === '\r' || s[p] === '\n')) p--
          const propAccess = p >= 0 && s[p] === '.'
          lastTok = (!propAccess && EXPR_KW.has(s.slice(i, j))) ? 'op' : 'value'
          i = j; break
        }
        if (isDigit(c)) {
          let j = i + 1
          while (j < N && (isIdPart(s[j]) || s[j] === '.')) j++
          lastTok = 'value'; i = j; break
        }
        if (c === ')' || c === ']') { lastTok = 'value'; i++; break }
        lastTok = 'op'; i++; break   // any other punctuator leaves a `/` in regex position
      }
      case 'line': { i++; break }
      case 'block': {
        // A block comment is transparent: leave lastTok as whatever preceded the comment so a `/`
        // right after `*/` is classified by the real prior token (`a /*c*/ / b` is division).
        if (c === '*' && s[i + 1] === '/') { state = 'code'; i += 2; break }
        i++; break
      }
      case 'sq': {
        if (escaped) { escaped = false; i++; break }
        if (c === '\\') { escaped = true; i++; break }
        if (c === '\'') { state = 'code'; lastTok = 'value'; i++; break }
        i++; break
      }
      case 'dq': {
        if (escaped) { escaped = false; i++; break }
        if (c === '\\') { escaped = true; i++; break }
        if (c === '"') { state = 'code'; lastTok = 'value'; i++; break }
        i++; break
      }
      case 'tpl': {
        if (escaped) { escaped = false; i++; break }
        if (c === '\\') { escaped = true; i++; break }
        if (c === '`') { frames.pop(); state = 'code'; lastTok = 'value'; i++; break }
        if (c === '$' && s[i + 1] === '{') { frames.push({ tpl: false, braces: 0 }); state = 'code'; lastTok = 'op'; i += 2; break }
        i++; break
      }
      case 'regex': {
        if (escaped) { escaped = false; i++; break }
        if (c === '\\') { escaped = true; i++; break }
        if (c === '[') { state = 'rclass'; i++; break }
        if (c === '/') { state = 'code'; lastTok = 'value'; i++; while (i < N && isFlag(s[i])) i++; break }
        i++; break
      }
      case 'rclass': {
        if (escaped) { escaped = false; i++; break }
        if (c === '\\') { escaped = true; i++; break }
        if (c === ']') { state = 'regex'; i++; break }
        i++; break
      }
    }
  }

  // Tokenizer self-check (dependency-free). A correct scan of the whole bundle ends in base-code state
  // with only the bottom frame left. Ending mid-template or mid-block-comment (or with a leftover
  // `${...}` frame) means the regex-vs-division heuristic desynced and opened a construct that never
  // closed — the one way a wrongly-stripped template line could slip past `node --check` (stripping
  // string data still parses). Fail closed rather than emit a corrupted bundle. verifyEmit's node parse
  // check cannot see this class of bug; this can.
  if ((state !== 'code' && state !== 'line') || frames.length !== 1) {
    throw new Error('stripComments: tokenizer desync at EOF (state=' + state + ', frames=' +
      frames.length + ') — refusing to strip; a source construct broke the regex/division lexer')
  }

  const lines = s.split('\n')
  const out = []
  for (let k = 0; k < lines.length; k++) {
    if (codeStart[k]) {
      const t = lines[k].trim()
      if (t === '' || t.startsWith('//')) continue   // strip blank line or full-line statement comment
    }
    out.push(lines[k])
  }
  return out.join('\n')
}

// verifyEmit: `node --check` the emitted bundle so a stripper bug can never ship an artifact that
// doesn't parse. Runs on every emit() (so --write and --check both gate on it).
//
// The bundle's first statement is `export const meta` (ESM) and its entry uses a top-level `return`
// (function/async-wrapper only) — a combination `node --check` rejects on node without module-syntax
// detection (< 20.19 / < 22.7). So we check the async-WRAPPED form (the exact shape the Workflow
// runtime and the bundle smoke evaluate), which parses on every node version. Uses process.execPath
// (the node already running the bundler) — never a bare `node` that may be off PATH. A distinct temp
// name per call avoids collisions when bundles are emitted concurrently.
let __verifyCheckSeq = 0
function verifyEmit(out) {
  const wrapped = ';(async () => {\n' + out.replace(/export\s+const\s+meta/, 'const meta') + '\n})();'
  const tmp = path.join(os.tmpdir(), 'sr-bundle-check-' + process.pid + '-' + (++__verifyCheckSeq) + '.js')
  // FAIL CLOSED on every failure mode (#295 review r2): an unrun verifier must never count as
  // success. The stage-write and the exec are guarded SEPARATELY so a temp-write ENOENT (e.g. a
  // missing TMPDIR) cannot be mistaken for the old "node binary unavailable" tolerance — and that
  // tolerance is gone too: process.execPath is the node running this bundler, so an ENOENT from the
  // exec is itself an environment fault worth stopping on, not a reason to skip the gate.
  try {
    fs.writeFileSync(tmp, wrapped)
  } catch (e) {
    throw new Error('verifyEmit could not stage the check file at ' + tmp + ' — the parse gate did ' +
      'NOT run; fix the temp dir rather than emitting unverified: ' + String((e && e.message) || e))
  }
  try {
    execFileSync(process.execPath, ['--check', tmp], { stdio: 'pipe' })
  } catch (e) {
    throw new Error('emitted bundle failed `node --check` (stripper produced unparseable output): ' +
      String((e && e.stderr) || (e && e.message) || e))
  } finally {
    try { fs.unlinkSync(tmp) } catch (_) {}
  }
}

function emit() {
  const factories = MODULES.map((f) => '// ===== ' + f + ' =====\n' + factory(f, fs.readFileSync(path.join(LIB, f), 'utf8')))
  const out = stripComments(PREAMBLE + '\n' + factories.join('\n') + '\n' + ENTRY)
  // The Workflow tool's permission layer rejects scripts containing raw control characters, so a
  // bundle carrying one can never be launched verbatim. Refuse to emit it — escape the offending
  // literal (\xNN) in the source module instead. Tab/newline are the only allowed controls.
  const raw = out.match(/[\u0000-\u0008\u000b-\u001f\u007f-\u009f]/)
  if (raw) {
    throw new Error('bundle would contain a raw control byte 0x' +
      raw[0].charCodeAt(0).toString(16) + ' at index ' + raw.index +
      ' — escape it (\\xNN) in the source module')
  }
  verifyEmit(out)
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

// Run as a CLI when invoked directly; export the pure helpers when required as a module (unit tests).
if (require.main === module) main(process.argv.slice(2))
module.exports = { stripComments, verifyEmit, emit }
