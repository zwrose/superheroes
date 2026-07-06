export const meta = {
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
  var m = p.match(/([\w-]+\.py)(?:\s+([a-z][\w-]*))?/)
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
function __q(s) { return "'" + String(s).replace(/'/g, "'\\''") + "'" }
function __sc(cmd) {
  var root = (typeof globalThis !== 'undefined' && globalThis.__SR_ROOT) ? String(globalThis.__SR_ROOT) : null
  if (!root) return cmd
  var t = String(cmd).replace(/^\s+/, '')
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
  var prompt = 'Execute this exact shell command via your command tool and return ONLY its stdout, unchanged. Do not echo, fence, summarize, or describe the command:\n\n' + __sc(cmd)
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
function __join() { return Array.prototype.slice.call(arguments).join('/').replace(/\/+/g, '/') }
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
// wraps the JSON in ``` (or single-backtick) fences or prose — a bare JSON.parse then silently
// defaults and the round-stamped pass evidence goes unseen (live wf_1ed21465-6f3: a clean verify round
// halted). Mirrors __helperResult's fence tolerance + extractJson's brace-slice: direct parse, then
// strip ONE wrapping fence pair (triple or single backtick), then a first-{…last-} brace slice. A
// genuinely empty answer (missing file: cat ... || true -> '') falls straight to the silent default
// (anti-fabrication: a missing verify file must NOT parse into a pass).
function __jsonFromText(t, dflt) {
  var s = String(t == null ? '' : t)
  if (!s.trim()) return dflt
  try { return JSON.parse(s) } catch (_) {}
  var stripped = s.replace(/^\s*```[a-zA-Z0-9]*\n?/, '').replace(/\n?```\s*$/, '').trim()
  if (/^\x60/.test(stripped) && /\x60$/.test(stripped)) {
    stripped = stripped.replace(/^\x60/, '').replace(/\x60$/, '').trim()
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
    // A misbehaving haiku courier STOCHASTICALLY wraps the whole answer in ``` fences (live
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
  const key = String(id).replace('./', '').replace(/\.js$/, '')   // MUST match the bundler's norm()
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

// ===== lib_root.js =====
__modules["lib_root"] = function (module, exports, require) {
// plugins/superheroes/lib/lib_root.js
// #170: the spine CODE root — where every `python3 <libRoot>/<cli>.py` compose points. It is the
// SECOND explicit root, distinct from the TARGET repo (`__SR_ROOT`, where git/build/docs operate):
// the code being EXECUTED and the repo being OPERATED ON are no longer assumed to be the same tree.
//
// Read at CALL time (never captured in a module-load const) from globalThis.__SR_LIB, which the
// bundle ENTRY plants from args.libRoot — the launching skill passes the versioned, immutable plugin
// cache (${CLAUDE_PLUGIN_ROOT}/lib), so a live run is pinned to its launch-time code version by
// construction. Absent (raw-module node smokes, a no-args launch, dev/dogfood) it falls back to the
// repo-relative path, which resolves under the leaf's `cd <root>` — so absent-libRoot composes stay
// BYTE-IDENTICAL to the pre-#170 spine.
'use strict'

const DEFAULT_LIB = 'plugins/superheroes/lib'

// libRoot: the resolved code-root string. globalThis exists in both node and the Workflow sandbox.
function libRoot() {
  const v = (typeof globalThis !== 'undefined') ? globalThis.__SR_LIB : null
  return (typeof v === 'string' && v.length) ? v : DEFAULT_LIB
}

// libPath: the interpreter-path segment for a shell compose — `python3 ${libPath('fence_cli.py')}`.
// With the default (relative) libRoot this yields the exact pre-#170 literal, so composes are byte-
// identical; with an absolute libRoot it yields the cache path (portable + cwd-independent).
function libPath(script) { return libRoot() + '/' + script }

// isAbsoluteLibRoot: true only when a caller planted an ABSOLUTE __SR_LIB (production / portable
// runs). The relative default (or any relative override) is treated as dev/dogfood mode.
function isAbsoluteLibRoot() { return libRoot().charAt(0) === '/' }

// _sq: POSIX single-quote a shell word (same escape as the spine's shq).
function _sq(s) { return "'" + String(s).replace(/'/g, "'\\''") + "'" }

// libRootProbe: a shell prefix that fail-closes when an ABSOLUTE spine code root has gone missing
// (e.g. a plugin-cache eviction between phases). It rides an ALREADY-composed command —
// `${libRootProbe()}python3 <lib>/recover_entry.py …` — so it adds NO leaf. When the dir is absent it
// echoes a PARSEABLE failure object carrying MISSING_MARKER, then __SR_EXIT:0, and exits 0; when
// present it is a no-op passthrough. In dev/dogfood mode (relative libRoot) it emits nothing, so the
// compose stays byte-identical.
//
// The payload is a JSON `{"ok":false,"reason":"<marker>"}` (not a bare echo) so BOTH probe sites map
// it to the same named park uniformly: the exec-based launch probe (reconcile) substring-matches the
// marker in raw stdout, and the runCourierMarkedJson-based back-half probe (persistPhase) gets it
// back verbatim as an `ok:false` failure only AFTER execution is proven via __SR_EXIT (#218). The
// failure branch must echo __SR_EXIT before exit — wrapMarkedCommand's trailing marker never runs
// after `exit 0`, and without an in-branch marker a genuine missing libRoot looks like a lazy parrot.
//
// Residual fabricability (#218): the __SR_EXIT guard proves a marker-SHAPED answer, not that Bash
// ran. This compose now embeds both the failure payload AND `echo __SR_EXIT:0` in the prompt, so a
// courier that SIMULATES the failure branch (payload + marker, no execution) would still pass the
// guard. Do NOT "harden" this with proof-of-execution (nonce/hash/timestamp) — the Workflow sandbox
// has no crypto, wall-clock, or RNG primitives, so the JS side cannot verify a computed proof; that
// is why #218 chose the marker protocol. The guard rejects the observed did-not-run shapes (bare
// payload with no marker; echoed command with literal __SR_EXIT:$?), and runCourierMarked*'s 2×3
// retry-then-default-dispatch chain bounds the residual simulation class.
const MISSING_MARKER = '__SR_LIBROOT_MISSING__'
function libRootProbe() {
  if (!isAbsoluteLibRoot()) return ''
  const payload = '{"ok":false,"reason":"' + MISSING_MARKER + '"}'
  return 'test -d ' + _sq(libRoot()) + " || { echo '" + payload + "'; echo __SR_EXIT:0; exit 0; }; "
}

// pyLibDir: a Python EXPRESSION that evaluates to the lib dir, for embedded
// `sys.path.insert(0, <pyLibDir()>)` scripts. Default mode reproduces the exact pre-#170 expression
// (byte-identical); an absolute libRoot becomes a bare string literal.
function pyLibDir() {
  const r = libRoot()
  return r === DEFAULT_LIB
    ? 'os.path.join(os.getcwd(), "plugins/superheroes/lib")'
    : JSON.stringify(r)
}

// pyLibScript: a Python string LITERAL for one lib script path, for embedded
// `subprocess.run(["python3", <pyLibScript('build_entry.py')>, …])`. Byte-identical in default mode.
function pyLibScript(name) { return JSON.stringify(libPath(name)) }

module.exports = {
  DEFAULT_LIB, libRoot, libPath, isAbsoluteLibRoot,
  libRootProbe, MISSING_MARKER, pyLibDir, pyLibScript,
}

};

// ===== cost_meter.js =====
__modules["cost_meter"] = function (module, exports, require) {
// plugins/superheroes/lib/cost_meter.js
// #130 token telemetry — a per-run, in-memory cost accumulator shared across the bundled spine via
// globalThis.__SR_COST. The bundle's agent wrapper calls record() on EVERY dispatch (the single
// choke-point) to tally the proxy — dispatch count × resolved model tier — under the current phase
// (globalThis.__SR_PHASE). runPhases calls mark(phase) at the phase boundary to baseline the output-
// token cursor; the phase's persist leaf calls take(phase) to snapshot the proxy counts + the budget-
// derived output-token delta, folded into the SAME durable write (no new leaf — #118). Pure +
// injectable: all state under globalThis; the budget is read via globalThis.__SR_BUDGET (bound by the
// preamble, injectable in tests). Never throws.

function _g() { return (typeof globalThis !== 'undefined') ? globalThis : {} }

function _state() {
  var g = _g()
  if (!g.__SR_COST || typeof g.__SR_COST !== 'object') g.__SR_COST = { phases: {}, starts: {} }
  if (!g.__SR_COST.starts) g.__SR_COST.starts = {}
  return g.__SR_COST
}

// record(model): count one dispatch under the current phase, keyed by the resolved model. The phase's
// OWN persist leaf (which writes the folded phase_cost) is excluded by ORDERING, not a flag: take()
// snapshots-and-resets the phase before that leaf dispatches, so the persist dispatch lands in a
// freshly-reset bucket that is never emitted (documented as an inherent exclusion in CONVENTIONS §4.6).
function record(model) {
  var s = _state()
  var phase = _g().__SR_PHASE || 'unknown'
  var p = s.phases[phase] || (s.phases[phase] = { dispatches: 0, byModel: {} })
  p.dispatches += 1
  var key = model || 'unknown'
  p.byModel[key] = (p.byModel[key] || 0) + 1
}

// readSpent(): the Workflow budget's cumulative OUTPUT-token cursor, or null when the runtime does
// not surface it (deterministic smokes, non-Workflow contexts). Guarded — never throws.
function readSpent() {
  var b = _g().__SR_BUDGET
  if (b && typeof b.spent === 'function') {
    try {
      var v = b.spent()
      return (typeof v === 'number' && isFinite(v)) ? v : null
    } catch (_) { return null }
  }
  return null
}

// mark(phase): baseline the output-token cursor at the phase boundary. take(phase) diffs against it.
function mark(phase) { _state().starts[phase] = readSpent() }

// take(phase): snapshot + RESET this phase's proxy counts, and compute the measured output-token
// delta since the phase's mark() (both endpoints must be finite numbers to count as measured).
// Returns the phase_cost payload body. Never throws.
function take(phase) {
  var s = _state()
  var p = s.phases[phase] || { dispatches: 0, byModel: {} }
  delete s.phases[phase]
  var startSpent = s.starts[phase]
  delete s.starts[phase]
  var endSpent = readSpent()
  var output = null, measured = false
  if (typeof startSpent === 'number' && isFinite(startSpent) &&
      typeof endSpent === 'number' && isFinite(endSpent)) {
    output = Math.max(0, endSpent - startSpent)
    measured = true
  }
  return {
    phase: phase,
    dispatches: { total: p.dispatches, byModel: p.byModel },
    tokens: { output: output, input: null, measured: measured, source: measured ? 'budget' : 'none' },
  }
}

// isEmpty(body): a phase with no dispatches AND no measured tokens — nothing worth recording.
function isEmpty(body) {
  return !!body && !body.dispatches.total && !body.tokens.measured
}

// reset(): clear all accumulated state (new-run guard / test helper).
function reset() { _g().__SR_COST = { phases: {}, starts: {} } }

module.exports = { record: record, readSpent: readSpent, mark: mark, take: take, isEmpty: isEmpty, reset: reset }

};

// ===== circuit_breaker.js =====
__modules["circuit_breaker"] = function (module, exports, require) {
// plugins/superheroes/lib/circuit_breaker.js
const { clampTitle, canonicalClassKey, classKeyAliases } = require('./review_memory.js')
const BLOCKING = new Set(['Critical', 'Important'])
// Python re.ASCII: \w == [A-Za-z0-9_], \s == [ \t\n\r\f\v]. Match those explicitly so JS \w/\s
// (which differ on unicode) cannot drift.
const _NON_WORD = /[^A-Za-z0-9_ \t\n\r\f\v]/g
const _WS = /[ \t\n\r\f\v]+/g
function normalizeTitle(title) {
  let t = String(title).toLowerCase()
  t = t.replace(_NON_WORD, '')
  t = t.replace(_WS, ' ')
  return t.trim()
}
function findingLabel(finding) {
  if (!finding || typeof finding !== 'object') return ''
  return finding.title || finding.summary || ''
}
function findingIdentity(finding) {
  return `${(finding && finding.file) || ''}::${normalizeTitle(clampTitle(findingLabel(finding)))}`
}
function recurrenceKey(finding) {
  if (finding && (finding.dimension || finding.taxonomy)) return canonicalClassKey(finding)
  if (finding && finding.classKey) return finding.classKey
  return findingIdentity(finding)
}
function recurrenceAliases(finding) {
  const aliases = new Set([recurrenceKey(finding)])
  if (finding && (finding.dimension || finding.taxonomy)) {
    for (const alias of classKeyAliases(finding)) aliases.add(alias)
  }
  return aliases
}
function intersects(a, b) {
  for (const x of a) if (b.has(x)) return true
  return false
}
function _blocking(round) { return round.findings.filter((f) => BLOCKING.has(f.severity)) }
function _roundRecordedFix(roundRec) {
  // Parity twin of circuit_breaker._round_recorded_fix: true when this round's fixer recorded
  // applied fixes (rec.fix.fixes). The cap-halt precedes the round's fix leg, so the latest round
  // usually carries no fix — keeps the max-iterations detail honest instead of always claiming one.
  const fix = roundRec && roundRec.fix
  if (!fix || typeof fix !== 'object') return false
  const fixes = fix.fixes
  return Array.isArray(fixes) ? fixes.length > 0 : !!fixes
}
function _generalizeKeys(roundRec) {
  return new Set((roundRec.generalizeRequired || []).filter((g) => g && g.classKey).map((g) => g.classKey))
}
function _blockingCountExcludingGeneralize(roundRec) {
  const generalize = _generalizeKeys(roundRec)
  const blocking = _blocking(roundRec)
  if (!generalize.size) return blocking.length
  return blocking.filter((f) => !intersects(recurrenceAliases(f), generalize)).length
}
function _roundReviewed(roundRec) {
  const dims = roundRec && roundRec.dimensions
  if (!dims || typeof dims !== 'object' || Array.isArray(dims)) return true
  const entries = Object.values(dims)
  if (!entries.length) return true
  return entries.some((d) => d && d.status === 'run')
}
function _reviewedRounds(rounds) {
  return (rounds || []).filter(_roundReviewed)
}
function checkCircuitBreaker(rounds, maxRounds) {
  const n = rounds.length
  if (n === 0) return { halt: false, reason: null, detail: 'no rounds yet' }
  const latest = _blocking(rounds[n - 1])
  if (n >= maxRounds && latest.length > 0) {
    // Honest halt detail (#212 class): name the ACTUAL round reached (n) alongside the cap — a resume
    // can run past the cap, so n may exceed maxRounds — and only claim "fixes committed" when the final
    // round actually recorded a fix. The cap-halt fires right after a review and before that round's
    // fixer runs, so the latest round usually carries no fix; saying otherwise misreads a park that
    // needs a fix-then-relaunch as one that only needs a re-review.
    const tail = _roundRecordedFix(rounds[n - 1])
      ? "the final round's fixes are committed but not yet re-reviewed"
      : 'no fix was applied this round — the finding(s) remain unaddressed'
    // Don't overstate how many REAL reviews ran: n counts every recorded round (the gate uses it),
    // but a transport-failed / all-missing round inflates it. When fewer rounds were actually reviewed
    // than recorded, say so (same honesty _reviewedRounds gives criteria 1-2).
    let capNote = `cap ${maxRounds}`
    const reviewedN = _reviewedRounds(rounds).length
    if (reviewedN < n) capNote += `, ${reviewedN} reviewed`
    return { halt: true, reason: 'max-iterations',
      detail: `Reached round ${n} (${capNote}); the latest review still showed ${latest.length} blocking finding(s) (${tail}).` }
  }
  const reviewed = _reviewedRounds(rounds)
  const rn = reviewed.length
  if (rn >= 3) {
    const cN = _blockingCountExcludingGeneralize(reviewed[rn - 1])
    const cN1 = _blockingCountExcludingGeneralize(reviewed[rn - 2])
    const cN2 = _blockingCountExcludingGeneralize(reviewed[rn - 3])
    if (cN > 0 && cN >= cN1 && cN1 >= cN2) {
      return { halt: true, reason: 'no-net-progress',
        detail: `Blocking-finding count did not decrease over two rounds (${cN2} → ${cN1} → ${cN}).` }
    }
  }
  if (rn >= 2) {
    const latestRec = reviewed[rn - 1]
    const latestGeneralize = new Set((latestRec.generalizeRequired || []).filter((g) => g && g.classKey).map((g) => g.classKey))
    const challenged = new Set((latestRec.coverageDecisions || []).filter((d) => d && d.classKey && d.challengedBy).map((d) => d.classKey))
    const latestBlocking = _blocking(latestRec)
    const prevIds = new Set()
    for (const f of _blocking(reviewed[rn - 2])) for (const alias of recurrenceAliases(f)) prevIds.add(alias)
    const recurring = latestBlocking.filter((f) => intersects(recurrenceAliases(f), prevIds))
    const challengedRecurring = recurring.filter((f) => intersects(recurrenceAliases(f), challenged))
    if (challengedRecurring.length) {
      const ids = challengedRecurring.map(recurrenceKey).join('; ')
      return { halt: true, reason: 'challenged-principle-recurring',
        detail: `${challengedRecurring.length} challenged coverage decision class recurred after being recorded: ${ids}` }
    }
    if (recurring.length) {
      const keys = new Set(recurring.map(recurrenceKey))
      for (const k of keys) {
        if (latestGeneralize.has(k)) {
          return { halt: false, reason: null, detail: 'recurrence pending coverage decision' }
        }
      }
      const ids = Array.from(keys).sort().join('; ')
      return { halt: true, reason: 'recurring-finding',
        detail: `${recurring.length} blocking finding(s) recurred after a fix was committed: ${ids}` }
    }
  }
  return { halt: false, reason: null, detail: 'progressing' }
}
module.exports = { normalizeTitle, findingIdentity, recurrenceKey, recurrenceAliases, checkCircuitBreaker, BLOCKING }

};

// ===== loop_state.js =====
__modules["loop_state"] = function (module, exports, require) {
// plugins/superheroes/lib/loop_state.js
function decide(blockingFixed, skippedBlocking, rnd, maxRounds, breakerHalt) {
  if (breakerHalt) {
    return ['halt', true, 'circuit breaker halted (stuck / recurrence) — stop and report the still-open findings and the commit range; do not loop further.']
  }
  if (blockingFixed > 0) {
    if (rnd >= maxRounds) {
      return ['halt', true, `round cap (${maxRounds}) reached with blocking fixes still landing — REPORT the open findings; do NOT declare success.`]
    }
    return ['review', true, `MANDATORY: ${blockingFixed} blocking (Critical/Important) finding(s) were addressed this round — re-review from scratch to verify they resolved and introduced nothing new. You may NOT exit, declare success, or offer the next round as 'optional'. The loop exists to verify fixes; your confidence that 'it is clean' is exactly what this gate overrides.`]
  }
  if (skippedBlocking > 0) {
    return ['exit_skipped', false, `no blocking finding addressed; ${skippedBlocking} blocking finding(s) were deliberately skipped — exit CLEAN-EXCEPT-FOR-SKIPPED: list the skipped blocker(s); do not report a plain success.`]
  }
  return ['exit_clean', false, 'no blocking findings to address and none skipped — the loop is genuinely done; exit SUCCESS.']
}
module.exports = { decide }

};

// ===== loop_synthesis.js =====
__modules["loop_synthesis"] = function (module, exports, require) {
// plugins/superheroes/lib/loop_synthesis.js
const { findingIdentity } = require('./circuit_breaker.js')
const _TIERS = new Set(['Critical', 'Important', 'Minor', 'Nit'])
const _BLOCKING = new Set(['Critical', 'Important'])
const _NON_BLOCKING = new Set(['Minor', 'Nit'])
const _DEFAULT_BLOCKING_SEVERITY = 'Important'

function _keptSeverity(f, v) {
  const verdictSeverity = (v && typeof v === 'object') ? v.severity : null
  if (_TIERS.has(verdictSeverity)) return verdictSeverity
  if (_TIERS.has(f && f.severity)) return f.severity
  return _DEFAULT_BLOCKING_SEVERITY
}

function consume(merged, leafVerdicts) {
  const byId = Object.create(null)   // null-proto: byId[identity] tests own keys only (Python dict parity)
  if (Array.isArray(leafVerdicts)) {
    for (const v of leafVerdicts) {
      if (v && typeof v === 'object' && typeof v.id === 'string') byId[v.id] = v
    }
  }
  const survivors = []; const drops = []; const downgrades = []
  for (const f of merged) {
    const id = findingIdentity(f)
    let v = byId[id]
    if (!v && f && typeof f.id === 'string') v = byId[f.id]
    const action = (v && typeof v === 'object') ? v.action : null
    const reason = (v && typeof v === 'object') ? v.reason : null
    if (action === 'drop' && typeof reason === 'string' && reason.trim()) {
      drops.push({ id, file: f.file === undefined ? null : f.file, title: f.title === undefined ? null : f.title,
        reason: reason.trim(), was_blocking_tagged: _BLOCKING.has(f.severity) })
      continue
    }
    const kept = Object.assign({}, f)
    kept.severity = _keptSeverity(f, v)
    survivors.push(kept)
    // DOWNGRADE-FLAG (#186): a survivor re-tiered from blocking to non-blocking rides recorded
    // (severity outcome unchanged) so the readout can flag it like a dropped blocker.
    const fromSeverity = f && f.severity
    if (_BLOCKING.has(fromSeverity) && _NON_BLOCKING.has(kept.severity)) {
      const entry = { id, file: f.file === undefined ? null : f.file,
        title: f.title === undefined ? null : f.title, from: fromSeverity, to: kept.severity }
      if (typeof reason === 'string' && reason.trim()) entry.reason = reason.trim()
      downgrades.push(entry)
    }
  }
  return { findings: survivors, drops, downgrades }
}
module.exports = { consume }

};

// ===== panel_tally.js =====
__modules["panel_tally"] = function (module, exports, require) {
// plugins/superheroes/lib/panel_tally.js
const { findingIdentity } = require('./circuit_breaker.js')
const loopState = require('./loop_state.js')
const BLOCKING = new Set(['Critical', 'Important'])
const SEV_RANK = { Critical: 0, Important: 1, Minor: 2, Nit: 3 }
const _ACTION_TO_TERMINAL = { review: 'continue', exit_clean: 'clean', exit_skipped: 'clean-with-skips', halt: 'halted' }

function _mergeDims(a, b) {
  const parts = []
  for (const src of [a.dimension, b.dimension]) {
    if (!src) continue
    for (let p of String(src).split('+')) { p = p.trim(); if (p && !parts.includes(p)) parts.push(p) }
  }
  return parts.join(' + ')
}
function compileFindings(findings, contextFiles) {
  const byId = Object.create(null)   // null-proto: `fid in byId` tests own keys only (Python dict parity)
  for (const f of findings) {
    if (f.file === null || f.file === undefined || f.line === null || f.line === undefined) continue
    if (contextFiles != null && !contextFiles.includes(f.file)) continue
    const fid = findingIdentity(f)
    if (fid in byId) {
      const ex = byId[fid]
      const dims = _mergeDims(ex, f)
      const merged = ((SEV_RANK[f.severity] != null ? SEV_RANK[f.severity] : 99) <
                      (SEV_RANK[ex.severity] != null ? SEV_RANK[ex.severity] : 99)) ? Object.assign({}, f) : Object.assign({}, ex)
      merged.dimension = dims
      byId[fid] = merged
    } else byId[fid] = Object.assign({}, f)
  }
  const out = Object.values(byId)
  for (const f of out) f.classification = f.tradeoff ? 'judgment' : 'mechanical'
  return out
}
function roundGate(compiled, expectedRoster, completedRoster) {
  const incomplete = expectedRoster.filter((r) => !completedRoster.includes(r))
  const hasBlocker = compiled.some((f) => BLOCKING.has(f.severity))
  let gate
  if (incomplete.length) gate = 'cannot-certify'
  else if (hasBlocker) gate = 'blocking'
  else gate = 'clean'
  const allVerifiable = compiled.every((f) => !!f.evidence)
  const confidence = (!incomplete.length && allVerifiable) ? 'high' : 'low'
  return { gate, confidence, incomplete }
}
function presentDeferred(compiled, deferredSet) {
  let n = 0
  for (const f of compiled) {
    if (!BLOCKING.has(f.severity)) continue
    const deferredSev = deferredSet[findingIdentity(f)]
    if (deferredSev === undefined || deferredSev === null) continue
    if ((SEV_RANK[f.severity] != null ? SEV_RANK[f.severity] : 99) >= (SEV_RANK[deferredSev] != null ? SEV_RANK[deferredSev] : 99)) n += 1
  }
  return n
}
function decideTerminal(gate, presentBlocking, presentDeferredCount, fixStatus, rnd, maxRounds, breakerHalt) {
  // FR-9 precedence (#212 fix-before-park): a cannot-certify round with NO fixable blocking finding
  // parks immediately (coverage is the sole gap). A cannot-certify round that STILL holds unresolved
  // blockers is NOT parked — its findings are real regardless of the uncertified seat, so it routes
  // to the fix leg like a `blocking` round (falls through). Gate-based, so it covers every entrance
  // to cannot-certify uniformly (receipt-missing/stale, a missing/malformed seat, a coverage-gap
  // round holding blockers). Certification stays withheld: the next round's gate re-dooms the seat.
  const blockingFixed = Math.max(0, presentBlocking - presentDeferredCount)
  if (gate === 'cannot-certify' && blockingFixed === 0) {
    return { terminal: 'cannot-certify', reason: 'coverage not certified — a review seat did not certify after its retry' }
  }
  if (fixStatus === 'failed') return { terminal: 'halted', reason: 'the fix step did not complete (failed or timed out)' }
  const [action, , reason] = loopState.decide(blockingFixed, presentDeferredCount, rnd, maxRounds, !!breakerHalt)
  return { terminal: _ACTION_TO_TERMINAL[action], reason }
}
// The defect-class phrasing that names WHY a seat could not certify (#212). Each class is a DISTINCT
// string so a park diagnoses the failure instead of anonymizing it.
const _SEAT_PHRASE = {
  'receipt-missing': (n) => `${n} returned no verification receipt after retry (receipt-missing — uncertifiable)`,
  'receipt-stale': (n) => `${n} returned a stale verification receipt after retry (receipt-stale — uncertifiable)`,
  malformed: (n) => `${n} did not return a usable result after retry (malformed — uncertifiable)`,
  'genuinely-incomplete': (n) => `${n} reported low confidence after retry (genuinely-incomplete — uncertifiable)`,
  'coverage-gap': (n) => `${n} did not complete after its retry (coverage-gap — uncertifiable)`,
}
function _seatDefectClass(result) {
  if (!result || typeof result !== 'object' || Array.isArray(result)) return 'coverage-gap'
  if (result.externalReview) return null
  if (result.confidence === 'high') return null
  if (result.receiptMissing) return 'receipt-missing'
  if (result.receiptStale) return 'receipt-stale'
  if ((result.status !== 'run' && result.status !== 'skipped') || result.malformed) return 'malformed'
  if (result.status === 'skipped') return 'coverage-gap'
  return 'genuinely-incomplete'
}
function uncertifiedReason(results, expectedRoster) {
  // The honest cannot-certify reason: name every seat that blocks certification AND why (#212).
  // Returns a `;`-joined phrase, or null when every seat certified (caller keeps the terminal reason).
  results = results || {}
  const parts = []
  for (const name of expectedRoster || []) {
    const cls = _seatDefectClass(results[name])
    if (cls) parts.push(_SEAT_PHRASE[cls](name))
  }
  return parts.length ? parts.join('; ') : null
}
function _currentBlockingFindings(results) {
  const out = []
  for (const [, result] of Object.entries(results || {})) {
    if (!result || result.status !== 'run') continue
    for (const f of Array.isArray(result.findings) ? result.findings : []) {
      if (!f || f.carried) continue
      if (BLOCKING.has(f.severity)) out.push(f)
    }
  }
  return out
}
function presentBlockingFromDimensionResults(results) {
  return _currentBlockingFindings(results).length
}
function blockingFindingsFromDimensionResults(results) {
  return _currentBlockingFindings(results).map((f) => Object.assign({}, f))
}
function compileDimensionResults(results) {
  const findings = []
  for (const [name, result] of Object.entries(results || {})) {
    if (!result || typeof result !== 'object' || Array.isArray(result)) continue
    for (const f of Array.isArray(result.findings) ? result.findings : []) {
      if (!f || typeof f !== 'object' || Array.isArray(f)) continue
      const item = Object.assign({}, f)
      if (!Object.prototype.hasOwnProperty.call(item, 'dimension')) item.dimension = result.dimension || name
      if (result.status === 'skipped') {
        item.carried = true
        item.sourceRound = result.carriedFromRound
      }
      findings.push(item)
    }
  }
  return compileFindings(findings)
}
function _validFinalReceipt(result, receiptContext) {
  const receipt = result && result.verificationReceipt
  if (!receipt || !receipt.artifact || !Array.isArray(receipt.coverageDecisionIds)) return false
  receiptContext = receiptContext || {}
  if (receiptContext.artifact && receipt.artifact !== receiptContext.artifact) return false
  const needed = new Set(receiptContext.coverageDecisionIds || [])
  const gotIds = new Set(receipt.coverageDecisionIds || [])
  for (const id of needed) if (!gotIds.has(id)) return false
  const chain = Array.isArray(receipt.chain) ? receipt.chain : []
  const got = new Set()
  for (const step of chain) {
    if (!step || typeof step !== 'object' || !step.evidence) return false
    got.add(step.step)
  }
  return ['citation', 'reachability', 'missing-check', 'tooling'].every((x) => got.has(x))
}
function roundGateFromDimensionResults(results, expectedRoster, finalConfirmation, receiptContext) {
  const completed = Object.entries(results || {})
    .filter(([, result]) => result.status === 'run' || result.status === 'skipped')
    .map(([name]) => name)
  const compiled = compileDimensionResults(results)
  const base = roundGate(compiled, expectedRoster, completed)
  for (const name of expectedRoster) {
    const result = (results || {})[name] || {}
    if (result.confidence !== 'high') return { gate: 'cannot-certify', confidence: 'low', incomplete: base.incomplete }
  }
  if (finalConfirmation) {
    for (const name of expectedRoster) {
      const result = (results || {})[name] || {}
      // externalReview (#38/receipt-fabrication fix): an external-engine reviewer has no native
      // chain-of-verification receipt to offer, but it IS a real independent review — accept it as
      // an alternate, honestly-labeled confirmation path instead of demanding a receipt shape it
      // structurally can't produce.
      if (result.externalReview) continue
      if (!_validFinalReceipt(result, receiptContext)) {
        return { gate: 'cannot-certify', confidence: 'low', incomplete: base.incomplete }
      }
    }
  }
  if (base.gate === 'clean' && _currentBlockingFindings(results).length > 0) {
    return { gate: 'blocking', confidence: base.confidence, incomplete: base.incomplete }
  }
  return base
}
module.exports = { compileFindings, roundGate, presentDeferred, decideTerminal, uncertifiedReason, compileDimensionResults, roundGateFromDimensionResults, presentBlockingFromDimensionResults, blockingFindingsFromDimensionResults, BLOCKING, SEV_RANK, _ACTION_TO_TERMINAL }

};

// ===== review_round_policy.js =====
__modules["review_round_policy"] = function (module, exports, require) {
// plugins/superheroes/lib/review_round_policy.js
const DEEP = 'reviewer-deep'
const CHEAP = 'reviewer'
// #174 confirmation-bar economics: at most this many FULL confirmation panels per loop, and the
// rework-breadth (distinct policy subjects the fix touched) at or above which a confirmation's
// rework counts as "cross-cutting" and re-arms one more full confirmation.
const MAX_CONFIRMATIONS = 2
const CROSS_CUTTING_SUBJECTS = 3
const SUBJECT_FALLBACK = {
  test: 'Test',
  security: 'Security',
  code: 'Code',
  architecture: 'Architecture',
  failure: 'Failure-Mode',
  premortem: 'Failure-Mode',
}
const POLICY_SUBJECTS = new Set(Object.values(SUBJECT_FALLBACK))

function _dim(prev, name) {
  if (!prev || typeof prev !== 'object' || Array.isArray(prev)) return {}
  const info = prev[name]
  return info && typeof info === 'object' && !Array.isArray(info) ? info : {}
}

function _changedSubjects(value) {
  if (!Array.isArray(value)) return null
  const out = []
  for (const item of value) {
    if (typeof item === 'string') {
      out.push(item)
      continue
    }
    if (item && typeof item === 'object' && !Array.isArray(item)) {
      for (const key of ['subject', 'dimension', 'policySubject']) {
        const subject = _policySubject(item[key])
        if (subject) out.push(subject)
      }
      // Section-only doc-reviser notes intentionally map to "known empty": cheap skips are bounded by the mandatory deep confirmation round.
      continue
    }
    return null
  }
  return Array.from(new Set(out))
}

function _policySubject(value) {
  if (typeof value !== 'string' || !value) return null
  if (POLICY_SUBJECTS.has(value)) return value
  return SUBJECT_FALLBACK[String(value || '').split('-')[0].toLowerCase()] || null
}

function _safeRound(value) {
  if (value === null || value === undefined || value === '') return { value: 1, malformed: false }
  if (typeof value === 'string' && value.includes('.')) return { value: 1, malformed: true }
  const n = Number(value)
  if (!Number.isFinite(n) || !Number.isInteger(n)) return { value: 1, malformed: true }
  return { value: n, malformed: false }
}

function _subjects(name, info) {
  if (Array.isArray(info.subjects)) return info.subjects.filter((s) => typeof s === 'string')
  const subjects = []
  for (const finding of Array.isArray(info.findings) ? info.findings : []) {
    if (finding && typeof finding.dimension === 'string') subjects.push(finding.dimension)
  }
  const fallback = SUBJECT_FALLBACK[String(name || '').split('-')[0].toLowerCase()]
  if (fallback) subjects.push(fallback)
  return Array.from(new Set(subjects))
}

function _hasFindings(info) {
  for (const value of [info.findings, info.currentFindings, info.carriedFindings]) {
    if (Array.isArray(value) && value.length > 0) return true
  }
  if (typeof info.hasFindings === 'boolean') return info.hasFindings
  if (Array.isArray(info.findings)) return info.findings.length > 0
  return null
}

function _subjectTouched(name, info, changedSubjects) {
  if (changedSubjects === null || changedSubjects === undefined) return null
  const subjects = _subjects(name, info)
  return subjects.some((s) => changedSubjects.includes(s))
}

function planRound(state) {
  state = state || {}
  const dimensions = Array.isArray(state.dimensions) ? state.dimensions : []
  const previous = state.previous && typeof state.previous === 'object' && !Array.isArray(state.previous) ? state.previous : {}
  const changedSubjects = _changedSubjects(state.changedSubjects)
  const parsedRound = _safeRound(state.round)
  const roundNo = parsedRound.value

  if (parsedRound.malformed) {
    const out = {}
    for (const d of dimensions) out[d] = { action: 'run', tier: DEEP, reason: 'malformed round state' }
    return { roundKind: 'intermediate', dimensions: out, escalationPolicy: 'deep-only' }
  }

  if (state.confirmation) {
    const out = {}
    for (const d of dimensions) out[d] = { action: 'run', tier: DEEP, reason: 'confirmation full-panel' }
    return { roundKind: 'confirmation', dimensions: out, escalationPolicy: 'deep-only' }
  }
  if (roundNo <= 1) {
    const out = {}
    for (const d of dimensions) out[d] = { action: 'run', tier: DEEP, reason: 'baseline full-panel' }
    return { roundKind: 'baseline', dimensions: out, escalationPolicy: 'deep-only' }
  }
  if (changedSubjects === null || changedSubjects === undefined) {
    const out = {}
    for (const d of dimensions) out[d] = { action: 'run', tier: DEEP, reason: 'unknown changed subjects' }
    return { roundKind: 'intermediate', dimensions: out, escalationPolicy: 'deep-only' }
  }

  const out = {}
  for (const name of dimensions) {
    const info = _dim(previous, name)
    const touched = _subjectTouched(name, info, changedSubjects)
    const hasFindings = _hasFindings(info)
    if (hasFindings === true || touched) {
      out[name] = { action: 'run', tier: CHEAP, reason: 'previous finding or changed subject' }
    } else if (info.confidence === 'high' && hasFindings === false) {
      out[name] = { action: 'skip', tier: DEEP, reason: 'high-confidence clean and untouched', carriedFromRound: info.round }
    } else {
      out[name] = { action: 'run', tier: DEEP, reason: 'not skip eligible' }
    }
  }
  return { roundKind: 'intermediate', dimensions: out, escalationPolicy: 'cheap-first' }
}

function isCrossCutting(changedSubjects, threshold = CROSS_CUTTING_SUBJECTS) {
  // #174: the rework of a confirmation's fix is "cross-cutting" when it touched at least
  // `threshold` distinct policy subjects (default ≥3 of the 5). Reuses the shared changed-subjects
  // normalizer, so a malformed / unknown surface returns null → treated as cross-cutting (fail
  // toward one more confirmation, never toward a premature certify).
  const subjects = _changedSubjects(changedSubjects)
  if (subjects === null || subjects === undefined) return true
  return new Set(subjects).size >= threshold
}

function confirmationFollowup(surfacedSeverities, confirmationsRun, crossCutting,
  maxConfirmations = MAX_CONFIRMATIONS) {
  // #174 confirmation-bar economics — the follow-up decision after a FULL confirmation panel
  // surfaced blocking findings (which the fix loop still resolves + verifies, requirement 1).
  // Only a Critical surfaced, OR cross-cutting rework, triggers one more full confirmation; hard
  // cap of `maxConfirmations` panels; a Critical still owed at the cap parks (certification
  // withheld), a non-Critical at the cap is resolved by a scoped verify then certified.
  const sevs = (surfacedSeverities || []).filter((s) => typeof s === 'string')
  const hasCritical = sevs.includes('Critical')
  const trigger = hasCritical || !!crossCutting
  const atCap = confirmationsRun >= maxConfirmations
  if (!trigger) {
    return { rearm: false, park: false, atCap,
      reason: 'non-Critical findings, rework not cross-cutting — resolve by scoped verify; no further confirmation panel' }
  }
  if (atCap) {
    if (hasCritical) {
      return { rearm: false, park: true, atCap: true,
        reason: 'Critical surfaced at the confirmation-panel cap — park; certification withheld' }
    }
    return { rearm: false, park: false, atCap: true,
      reason: 'confirmation-panel cap reached — resolve remaining by scoped verify; no further panel' }
  }
  return { rearm: true, park: false, atCap: false,
    reason: (hasCritical ? 'Critical surfaced by confirmation' : 'cross-cutting rework') + ' — one more full confirmation panel required' }
}

module.exports = { planRound, isCrossCutting, confirmationFollowup, MAX_CONFIRMATIONS, CROSS_CUTTING_SUBJECTS }

};

// ===== ci_status.js =====
__modules["ci_status"] = function (module, exports, require) {
// plugins/superheroes/lib/ci_status.js
// Parity twin of ci_status.py — green / red / pending / none. Pending is its own status
// (0.10.0 qualification finding: pending-as-red made the ship loop dispatch a CI fixer at
// checks that were merely running). Pending means WAIT, red means FIX, neither is green.
const _PASS = new Set(['pass', 'success', 'skipping', 'skipped', 'neutral'])
const _PENDING = new Set(['pending', 'queued', 'in_progress', 'expected', 'waiting', 'requested'])
function _bucket(item) {
  if (!item || typeof item !== 'object') return 'unknown'
  return String(item.bucket || item.state || item.conclusion || 'unknown').toLowerCase()
}
function classify(checks) {
  if (!Array.isArray(checks) || checks.length === 0) return { status: 'none', failing: [], pending: [] }
  const failing = []
  const pending = []
  let sawGating = false
  for (const item of checks) {
    const b = _bucket(item)
    const name = (item && typeof item === 'object') ? item.name : null
    if (b === 'skipping' || b === 'skipped' || b === 'neutral') continue
    sawGating = true
    if (_PASS.has(b)) continue
    if (_PENDING.has(b)) pending.push(name || 'unknown')
    else failing.push(name || 'unknown')
  }
  if (failing.length) return { status: 'red', failing, pending }
  if (pending.length) return { status: 'pending', failing: [], pending }
  if (!sawGating) return { status: 'none', failing: [], pending: [] }
  return { status: 'green', failing: [], pending: [] }
}
module.exports = { classify }

};

// ===== verify_gate.js =====
__modules["verify_gate"] = function (module, exports, require) {
// plugins/superheroes/lib/verify_gate.js
// JS twin of verify_gate.py's returncode->result classification (the subprocess RUN stays an
// executor; this is the pure mapping it feeds). 'none'/'' command -> skipped; timeout -> timeout;
// returncode 0 -> pass; else fail. Fail-closed: anything not unambiguously a pass is fail.
// Defense-in-depth: tolerates courier-stringified fields (returncode:'0', timedOut:'false').
function classify(runResult) {
  const r = runResult || {}
  const cmd = r.command
  if (!cmd || String(cmd).trim().toLowerCase() === 'none') return 'skipped'
  // Tolerate stringified timedOut: truthy iff boolean true or string 'true' (case-insensitive).
  // A stringified 'false' is NOT timed out (the original bug: any non-empty string was truthy).
  const timedOut = r.timedOut === true || String(r.timedOut).toLowerCase() === 'true'
  if (timedOut) return 'timeout'
  // Tolerate a stringified returncode: pass iff an unambiguous integer 0 (numeric 0 or the string
  // '0'). Fail-CLOSED on anything that is not a plain integer string — crucially the empty string,
  // because Number('')===0 (and Number('  ')===0, Number(null)===0). An empty/whitespace/dropped
  // returncode is a plausible courier garble — exactly the corruption this layer exists to catch —
  // and must NEVER read as a pass. Match an integer string first; everything else (''/NaN/null/
  // undefined/missing) -> fail.
  const rcStr = String(r.returncode).trim()
  if (!/^-?\d+$/.test(rcStr)) return 'fail'
  return Number(rcStr) === 0 ? 'pass' : 'fail'
}
module.exports = { classify }

};

// ===== review_memory.js =====
__modules["review_memory"] = function (module, exports, require) {
// plugins/superheroes/lib/review_memory.js
const BLOCKING = new Set(['Critical', 'Important'])

function _norm(value) {
  return String(value || '').trim().toLowerCase().replace(/\s+/g, ' ')
}

const _MAX_TITLE = 160
const _TITLE_ELLIPSIS = '...'
function clampTitle(title) {
  if (typeof title !== 'string') return title
  if (title.length <= _MAX_TITLE) return title
  const limit = _MAX_TITLE - _TITLE_ELLIPSIS.length
  let prefix = title.slice(0, limit).replace(/[ \t\n\r\f\v]+$/, '')
  let boundary = -1
  for (const ch of [' ', '\t', '\n', '\r', '\f', '\v']) boundary = Math.max(boundary, prefix.lastIndexOf(ch))
  if (boundary > 0) prefix = prefix.slice(0, boundary).replace(/[ \t\n\r\f\v]+$/, '')
  if (!prefix) prefix = title.slice(0, limit).replace(/[ \t\n\r\f\v]+$/, '')
  return prefix + _TITLE_ELLIPSIS
}

function _titleText(finding) {
  if (!finding || typeof finding !== 'object') return ''
  return finding.title || finding.summary || ''
}

function classKey(finding) {
  finding = finding || {}
  return `${finding.dimension || ''}::${finding.taxonomy || ''}::${_norm(clampTitle(_titleText(finding)))}`
}

function canonicalClassKey(finding) {
  if (!finding || typeof finding !== 'object') return classKey({})
  if (finding.title || finding.summary || finding.dimension || finding.taxonomy) return classKey(finding)
  return finding.classKey || classKey(finding)
}

function classKeyAliases(finding) {
  const aliases = new Set([canonicalClassKey(finding)])
  if (finding && typeof finding === 'object' && finding.classKey) aliases.add(finding.classKey)
  return aliases
}


function recurrentClasses(records, coverageDecisions) {
  const covered = new Set((coverageDecisions || []).map((d) => d && d.classKey).filter(Boolean))
  const seen = Object.create(null)
  for (const rec of records || []) {
    for (const finding of (rec && rec.findings) || []) {
      if (finding.carried) continue
      if (!BLOCKING.has(finding.severity)) continue
      const key = canonicalClassKey(finding)
      let isCovered = false
      for (const alias of classKeyAliases(finding)) if (covered.has(alias)) isCovered = true
      if (isCovered) continue
      if (!seen[key]) seen[key] = new Set()
      seen[key].add(rec.round)
    }
  }
  return Object.keys(seen).sort()
    .filter((k) => seen[k].size >= 2)
    .map((k) => ({ classKey: k, rounds: Array.from(seen[k]).sort((a, b) => a - b) }))
}

function promoteRecord(record, dimensions) {
  record = record || {}
  if (record.schemaVersion === 2) return record
  const dims = {}
  for (const d of dimensions || []) dims[d] = { dimension: d, status: 'unknown' }
  return {
    schemaVersion: 2,
    round: record.round,
    kind: 'unknown',
    dimensions: dims,
    findings: Array.isArray(record.findings) ? record.findings : [],
    changedSubjects: null,
    coverageDecisions: [],
    tokenUsage: { available: false, reason: 'promoted from schema v1' },
    confirmationPending: false,
  }
}

function recordFromDimensionResults(roundNo, kind, dimensions, changedSubjects, coverageDecisions, tokenUsage, confirmationPending) {
  const findings = []
  const carriedFindings = []
  const dimensionRecords = {}
  const subjectFallback = { test: 'Test', security: 'Security', code: 'Code', architecture: 'Architecture', failure: 'Failure-Mode' }
  for (const [name, result] of Object.entries(dimensions || {})) {
    const out = Object.assign({ dimension: name, round: roundNo }, result || {})
    const current = []
    const carried = []
    const isCarried = out.status === 'skipped' || out.carriedFromRound !== undefined
    for (const raw of Array.isArray(out.findings) ? out.findings : []) {
      const item = Object.assign({ dimension: out.dimension || name }, raw)
      if (isCarried) {
        item.carried = true
        item.sourceRound = out.carriedFromRound || item.sourceRound || roundNo
        carried.push(item)
      } else {
        current.push(item)
      }
    }
    const subjects = new Set([...current, ...carried].map((f) => f.dimension).filter(Boolean))
    const fallback = subjectFallback[String(name || '').split('-')[0].toLowerCase()]
    if (fallback) subjects.add(fallback)
    out.findings = current.concat(carried)
    out.currentFindings = current
    out.carriedFindings = carried
    out.hasFindings = current.length + carried.length > 0
    out.subjects = Array.from(subjects).sort()
    dimensionRecords[name] = out
    findings.push(...current)
    carriedFindings.push(...carried)
  }
  return {
    schemaVersion: 2,
    round: roundNo,
    kind,
    dimensions: dimensionRecords,
    findings,
    carriedFindings,
    changedSubjects,
    coverageDecisions: coverageDecisions || [],
    tokenUsage: tokenUsage || { available: false, reason: 'missing' },
    confirmationPending: !!confirmationPending,
  }
}

// skeletonRecord: the JS twin of review_memory.py summarize_record — the bounded durable form
// of a round record (D3). Findings keep only identity/class/severity (title<=160); dimension
// records keep their scheduling scalars + skeleton findings. This is what persist-skeleton
// ships inline (Python re-applies summarize_record on arrival, so a drift here can widen the
// leaf payload but can never widen the on-disk contract).
const _SKELETON_FIELDS = ['file', 'line', 'title', 'severity', 'taxonomy', 'dimension',
                          'classKey', 'carried', 'sourceRound', 'synthesisUnverified']
function _skeletonFinding(finding) {
  if (!finding || typeof finding !== 'object') return {}
  const out = {}
  for (const k of _SKELETON_FIELDS) if (k in finding) out[k] = finding[k]
  if (typeof out.title === 'string') out.title = clampTitle(out.title)
  // A stored classKey is preserved verbatim (legacy unclamped-title keys must survive
  // skeletonization for classKeyAliases to match legacy coverage decisions); only a
  // key-less finding gets the canonical stamp.
  if (!('classKey' in out) && (finding.dimension || finding.taxonomy)) out.classKey = canonicalClassKey(finding)
  return out
}

function _summarizeDimension(dim) {
  if (!dim || typeof dim !== 'object') return {}
  const findings = Array.isArray(dim.findings) ? dim.findings : []
  const out = {}
  // `usage` is a small scalar object ({total,input,output}); the skeleton keeps it so a carried
  // (skipped) dimension carries its prior round's usage forward and the telemetry stays complete
  // (#211: the loop reads the carried dim from the durable skeleton, not an in-memory copy).
  for (const k of ['dimension', 'status', 'confidence', 'round', 'subjects',
                   'carriedFromRound', 'escalated', 'tier', 'usage']) if (k in dim) out[k] = dim[k]
  out.findings = findings.map(_skeletonFinding)
  out.hasFindings = findings.length > 0 || !!dim.hasFindings
  out.blockingCount = findings.filter((f) => f && typeof f === 'object' && BLOCKING.has(f.severity)).length
  return out
}

// skeletonDeferred: the JS twin of _skeleton_deferred — deferred entries ride the update-round
// delta as identity/severity/reason (+ skeleton finding); the full bodies' durable home is the
// best-effort round-bodies dump.
const _MAX_DEFER_REASON = 500
const _MAX_COVERAGE_TEXT = 500
const _COVERAGE_FIELDS = ['id', 'classKey', 'kind', 'sourceRound', 'challengedBy', 'text', 'source']

function skeletonDeferred(items) {
  const out = []
  for (const item of Array.isArray(items) ? items : []) {
    if (!item || typeof item !== 'object') { out.push(item); continue }
    const slim = {}
    for (const k of ['identity', 'id', 'severity', 'reason']) if (k in item) slim[k] = item[k]
    if (typeof slim.reason === 'string' && slim.reason.length > _MAX_DEFER_REASON) slim.reason = slim.reason.slice(0, _MAX_DEFER_REASON)
    if (item.finding && typeof item.finding === 'object' && !Array.isArray(item.finding)) slim.finding = _skeletonFinding(item.finding)
    out.push(slim)
  }
  return out
}

// skeletonCoverageDecisions: the JS twin of _skeleton_coverage_decisions — coverage decision
// text is unbounded in the fix loop but must not ride the courier-staged update-round delta
// whole. Identity/class/source fields pass through; text is bounded at persist time. The in-memory
// record keeps the full text for the current session's fix context.
function skeletonCoverageDecisions(items) {
  const out = []
  for (const item of Array.isArray(items) ? items : []) {
    if (!item || typeof item !== 'object') { out.push(item); continue }
    const slim = {}
    for (const k of _COVERAGE_FIELDS) if (k in item) slim[k] = item[k]
    if (typeof slim.text === 'string' && slim.text.length > _MAX_COVERAGE_TEXT) slim.text = slim.text.slice(0, _MAX_COVERAGE_TEXT)
    out.push(slim)
  }
  return out
}

function skeletonRecord(record) {
  const rec = (record && typeof record === 'object') ? record : {}
  const findings = Array.isArray(rec.findings) ? rec.findings : []
  const carried = Array.isArray(rec.carriedFindings) ? rec.carriedFindings : []
  const dims = {}
  for (const [name, d] of Object.entries(rec.dimensions || {})) dims[name] = _summarizeDimension(d)
  return {
    schemaVersion: rec.schemaVersion === undefined ? null : rec.schemaVersion,
    round: rec.round === undefined ? null : rec.round,
    kind: rec.kind === undefined ? null : rec.kind,
    confirmationPending: !!rec.confirmationPending,
    changedSubjects: rec.changedSubjects === undefined ? null : rec.changedSubjects,
    coverageDecisions: skeletonCoverageDecisions(rec.coverageDecisions || []),
    tokenUsage: rec.tokenUsage === undefined ? null : rec.tokenUsage,
    findings: findings.map(_skeletonFinding),
    carriedFindings: carried.map(_skeletonFinding),
    dimensions: dims,
  }
}

module.exports = { clampTitle, classKey, canonicalClassKey, classKeyAliases, recurrentClasses, promoteRecord, recordFromDimensionResults, skeletonRecord, skeletonDeferred, skeletonCoverageDecisions }

};

// ===== review_panel_shell.js =====
__modules["review_panel_shell"] = function (module, exports, require) {
// review_panel_shell.js — the reusable review-panel + loop-to-clean orchestration shell (#86, #115).
//
// CONTROL FLOW ONLY. Every judgement (compile, gate, confidence, the four loop terminals, the
// fix-failure -> halted decision, the circuit breaker) lives in the parity-locked pure-decider
// twins (panel_tally / loop_synthesis / circuit_breaker / loop_state); this shell detects events and
// forwards them IN MEMORY. The shell makes exactly one branch: `if (terminal !== 'continue')`.
const { io } = require('./io_seam.js')
const panelTally = require('./panel_tally.js')
const loopSynthesis = require('./loop_synthesis.js')
const circuitBreaker = require('./circuit_breaker.js')
const loopState = require('./loop_state.js')
const verifyGateTwin = require('./verify_gate.js')
const reviewMemory = require('./review_memory.js')
const { libPath } = require('./lib_root.js')   // #170: spine code root for lib composes

const SCHEMA_VERSION = 1
const BLOCKING = new Set(['Critical', 'Important'])
const POLICY_SUBJECTS = new Set(['Test', 'Security', 'Code', 'Architecture', 'Failure-Mode'])

// ── #211 decider leaves (couriers): the shell asks the Python deciders "what now?" and receives
// small meaningful JSON — never findings. Each reads the durable round-records.json from disk; the
// scalars the durable skeleton can't hold (gate/present-blocking/uncertified reason) ride DOWN as
// args. A mangled/unparseable answer returns null → the caller fails closed (the decider's
// documented direction). Cheap tier (`courier: true`); the answers carry no oversized payload.
function _jsonAnswer(out) {
  try { const p = JSON.parse((out && out.stdout) || ''); return (p && typeof p === 'object') ? p : null }
  catch (_) { return null }
}

async function planRoundDecider({ runDir, round, roster, changedSubjects, justMarked, coverageTarget, ioApi }) {
  const args = [libPath('review_loop_plan.py'), 'plan-round',
    '--path', ioApi.join(runDir, 'round-records.json'),
    '--round', String(round),
    '--dimensions', JSON.stringify(roster || [])]
  if (coverageTarget) args.push('--coverage-path', coverageTarget.path, '--coverage-mode', coverageTarget.mode)
  if (changedSubjects !== null && changedSubjects !== undefined) args.push('--changed-subjects', JSON.stringify(changedSubjects))
  if (justMarked) args.push('--just-marked')
  for (let attempt = 0; attempt < 2; attempt += 1) {
    const ans = _jsonAnswer(await ioApi.runHelper('python3', args, { label: 'plan review round', courier: true }))
    if (ans && ans.ok) return ans
  }
  return null
}

async function tallyRoundDecider({ runDir, round, roster, maxRounds, gate, confidence, missing,
  presentBlocking, uncertifiedReason, fixStatus, verifyResult, enterConfirmation, coverageTarget,
  worklistOutPath, ioApi }) {
  const args = [libPath('review_loop_plan.py'), 'tally-round',
    '--path', ioApi.join(runDir, 'round-records.json'),
    '--round', String(round),
    '--roster', JSON.stringify(roster || []),
    '--max-rounds', String(maxRounds),
    '--gate', gate,
    '--confidence', confidence,
    '--missing', JSON.stringify(missing || []),
    '--present-blocking', String(presentBlocking || 0),
    '--deferred-path', deferredSetPath(runDir),
    '--fix-status', fixStatus || 'completed']
  if (coverageTarget) args.push('--coverage-path', coverageTarget.path, '--coverage-mode', coverageTarget.mode)
  if (worklistOutPath) args.push('--worklist-out-path', worklistOutPath)
  if (verifyResult !== null && verifyResult !== undefined) args.push('--verify-result', String(verifyResult))
  if (enterConfirmation) args.push('--enter-confirmation')
  if (uncertifiedReason) args.push('--uncertified-reason', uncertifiedReason)
  for (let attempt = 0; attempt < 2; attempt += 1) {
    const ans = _jsonAnswer(await ioApi.runHelper('python3', args, { label: 'tally review round', courier: true }))
    if (ans && typeof ans.terminal === 'string') return ans
  }
  return null
}

function _usable(v) { return v && typeof v.terminal === 'string' }
function _failClosed() {
  return { schemaVersion: SCHEMA_VERSION, terminal: 'halted', recordMissing: true,
           reason: 'tally produced no usable verdict — failing closed' }
}

function deferredSetPath(runDir) { return `${runDir}/deferred-set.json` }
// (#211: the JS loadDeferredSet is gone — the tally decider reads deferred-set.json Python-side via
// --deferred-path, fail-soft to {}. This retired the review loop's last prose-vulnerable JS read.)

function reviewerContext(context, coverageDecisions, receiptContext) {
  return Object.assign({}, context || {}, { coverageDecisions: coverageDecisions || [], receiptContext })
}

function annotateChallengedCoverage(coverageDecisions, roundFindings, reviewerSet) {
  const known = new Set((coverageDecisions || []).map((d) => d && d.classKey).filter(Boolean))
  const out = (coverageDecisions || []).map((d) => Object.assign({}, d))
  const byClass = Object.fromEntries(out.filter((d) => d.classKey).map((d) => [d.classKey, d]))
  for (const name of reviewerSet || []) {
    const result = roundFindings[name]
    if (!result || result.status !== 'run') continue
    for (const f of result.findings || []) {
      if (!BLOCKING.has(f.severity)) continue
      const key = f.classKey || reviewMemory.classKey(f)
      if (!known.has(key)) continue
      const decision = byClass[key]
      if (decision) decision.challengedBy = name
    }
  }
  return out
}

// #211: the entry read (gatherReviewSetup) rides DECISIONS, so its answer is normally a small direct
// blob. The receipt+chunk transport survives as the EMERGENCY FALLBACK only — an answer that
// unexpectedly outgrows the receipt bound (e.g. a coverage-decision list that has grown large): the
// helper writes the blob to disk Python-side and answers a small receipt, and the shell reassembles it
// via read-chunk. Each chunk ships as RAW TEXT (a readable JSON fragment), not base64 — run-5 evidence
// showed the API safety layer REFUSES an opaque base64-shaped blob as a model answer, and an earlier
// run showed a courier decoding a b64 payload (decode-bait). The reader verifies each chunk's
// chunkHash (over the text exactly as shipped) plus the reconstructed content hash before parsing, so
// any retype still fails closed.
const _SUMMARY_RECEIPT_BOUND = 4000
const _READ_CHUNK_CHARS = 4000

function _jsonFromStdout(out) {
  try { return JSON.parse((out && out.stdout) || '') } catch (_) { return null }
}

// #211: each chunk ships as RAW TEXT (`text`, the on-disk slice verbatim), not a reversed-base64
// blob. run-5 evidence showed the API safety layer refuses an opaque base64-shaped answer, and an
// earlier run showed a courier decoding a b64 payload (decode-bait) — a readable JSON fragment has
// nothing to unwrap and pattern-matches as benign. The chunkHash covers the text exactly as shipped,
// so a courier that retypes or "fixes" the slice breaks the hash and the read fails closed, and the
// reconstructed-content-hash check at the end still guards the full reassembly.
async function _readReceiptText(ioApi, receipt, expectedReceipt, corruptReason) {
  if (!receipt || receipt.receipt !== expectedReceipt || !receipt.path || !receipt.contentHash) return { ok: false, reason: corruptReason }
  const chunkSize = receipt.chunkSize || _READ_CHUNK_CHARS
  let index = 0
  let text = ''
  for (let guard = 0; guard < 10000; guard += 1) {
    let parsed = null
    for (let attempt = 0; attempt < 3; attempt += 1) {
      // payload marker: chunk answers are ~2KB relay payloads — they ride the copy-faithful
      // payload tier, not the cheapest courier tier (#191 gap: the read leg missed the pin).
      const out = await ioApi.runHelper('python3', [libPath('review_memory.py'), 'read-chunk', '--path', receipt.path, '--index', String(index), '--chunk-size', String(chunkSize)], { payload: true })
      parsed = _jsonFromStdout(out)
      if (!parsed || !parsed.ok || parsed.index !== index) { parsed = null; continue }
      if (parsed.contentHash !== receipt.contentHash) { parsed = null; continue }
      if (typeof parsed.text !== 'string' || parsed.chunkHash !== ioApi.contentHash(parsed.text)) { parsed = null; continue }
      break
    }
    if (!parsed) return { ok: false, reason: corruptReason }
    text += parsed.text
    if (parsed.eof) break
    index = Number(parsed.nextIndex)
    if (!Number.isFinite(index)) return { ok: false, reason: corruptReason }
  }
  if (ioApi.contentHash(text) !== receipt.contentHash) return { ok: false, reason: corruptReason }
  return { ok: true, text }
}

// D3: the DURABLE round record is the bounded SKELETON (review_memory.skeletonRecord — evidence
// bodies and receipts stripped, finding identity/class/severity kept), persisted in ONE verified
// CAS leaf for the typical
// round: the skeleton rides the courier args inline, self-verified by --record-hash =
// sha256(record-json) — a courier that mangles the JSON cannot also recompute its hash, so
// corruption fails closed as record-corrupt (one retry, then cannot-certify upstream) instead
// of persisting silently altered content. A many-finding round whose skeleton outgrows a safe
// inline arg falls back to a staged file (+1 unverified stage leaf; the same hash check covers
// it). Python re-applies summarize_record on arrival, so evidence bodies can never land in
// round-records.json even if the JS twin drifts. Full bodies of the audit targets
// (dropped/deferred findings) ride the separate BEST-EFFORT round-bodies dump; the final
// round's bodies live in terminal-record.json.
const _INLINE_RECORD_BOUND = 6000

// _selfVerifiedHelper: run a review_memory.py write verb whose payload self-verifies in
// transport (--…-hash = sha256 of the exact text). Retries ONCE on a transport-corrupt
// payload or an unparseable answer; a real refusal (stale/unreadable/round-missing) is
// final. The helper side answers ok-idempotently when a prior attempt already persisted
// this exact write and only its ANSWER was lost — so the retry-after-mangled-answer path
// converges instead of dying 'stale'.
async function _selfVerifiedHelper(ioApi, args, stagedPath, stagedText, corruptReason) {
  for (let attempt = 0; attempt < 2; attempt += 1) {
    let out
    if (stagedPath) {
      try {
        out = await ioApi.stageAndRunHelper(stagedPath, stagedText, 'python3', args)
      } catch (_) {
        // a missing parent dir is the common first-attempt failure (fresh run dir); create it
        // and let the retry re-stage.
        const dir = String(stagedPath).slice(0, String(stagedPath).lastIndexOf('/'))
        if (dir) { try { await ioApi.mkdirp(dir) } catch (_e) { /* the retry fails closed */ } }
        continue
      }
    } else {
      out = await ioApi.runHelper('python3', args)
    }
    let parsed = null
    try { parsed = JSON.parse((out && out.stdout) || '') } catch (_) { parsed = null }
    if (parsed && parsed.ok) return parsed
    if (parsed && parsed.reason && parsed.reason !== corruptReason) return { ok: false, reason: parsed.reason }
  }
  return { ok: false, reason: 'helper-failed' }
}

async function persistRoundRecord(runDir, reviewerSet, record, expectedHash, runId, lease, ioApi) {
  const recordJson = JSON.stringify(reviewMemory.skeletonRecord(record))
  const inline = recordJson.length <= _INLINE_RECORD_BOUND
  const stagedPath = inline ? null : ioApi.join(runDir, `round-skeleton-r${record.round}.json`)
  const args = [libPath('review_memory.py'), 'persist-skeleton',
    '--path', ioApi.join(runDir, 'round-records.json')]
  args.push(...(inline ? ['--record-json', recordJson] : ['--record-path', stagedPath]))
  args.push('--record-hash', ioApi.contentHash(recordJson),
    '--round', String(record.round), '--dimensions', JSON.stringify(reviewerSet || []),
    '--expected-hash', expectedHash || ioApi.contentHash(''), '--run-id', runId)
  if (lease) args.push('--lease', lease)
  return _selfVerifiedHelper(ioApi, args, stagedPath, recordJson, 'record-corrupt')
}

// D3 best-effort forensics: the FULL bodies of this round's dropped + deferred findings — the
// audit targets (UFR-10 dropped-blocker evidence, receipt trust audits). A fixed finding's
// evidence is its fix commit, so fixed bodies don't ride. ONE fire-and-forget leaf under the
// spec's FR-4 best-effort carve-out: nothing advances on this write, so a failed (or
// courier-mangled) dump degrades the audit trail, never the run.
async function dumpRoundBodiesBestEffort(runDir, round, verdict, fixReport, ioApi) {
  const drops = (verdict && Array.isArray(verdict.drops)) ? verdict.drops : []
  const deferred = (fixReport && Array.isArray(fixReport.deferred)) ? fixReport.deferred : []
  if (!drops.length && !deferred.length) return
  try {
    await ioApi.writeFile(ioApi.join(runDir, `round-bodies-r${round}.json`),
      JSON.stringify({ schemaVersion: 1, round, drops, deferred }))
  } catch (_) { /* best-effort by contract */ }
}

// (#211: mergeRoundRecords is gone — the shell no longer keeps an in-memory records copy; the
// durable skeleton on disk is the single source of truth the deciders read.)

// The post-fix update ships only the SMALL delta (confirmation marker, changed subjects,
// coverage decisions, fix summary) — never the round body — via review_memory.py update-round,
// self-verified in transport like persist-skeleton (--updates-hash; staged-file fallback past
// the safe inline size — the delta is usually small but coverageDecisions/fixes are unbounded).
// Deferred entries ride slimmed (identity/severity/reason + skeleton finding): their full
// bodies go to the round-bodies dump, not through this pipe or into round-records.json.
async function persistPostFixRecord(runDir, reviewerSet, round, fixResult, recordedCoverageDecisions, expectedHash, runId, lease, ioApi, legKind) {
  const updates = {
    changedSubjects: fixResult.changedSubjects || [],
    coverageDecisions: reviewMemory.skeletonCoverageDecisions(recordedCoverageDecisions || []),
    fix: {
      fixes: fixResult.fixes || fixResult.fixed || [],
      deferred: reviewMemory.skeletonDeferred(fixResult.deferred || []),
      changedSubjectDetails: fixResult.changedSubjectDetails || [],
    },
  }
  if (legKind && legKind.panel) updates.confirmationPending = true
  const updatesJson = JSON.stringify(updates)
  const inline = updatesJson.length <= _INLINE_RECORD_BOUND
  const stagedPath = inline ? null : ioApi.join(runDir, `round-updates-r${round}.json`)
  const args = [libPath('review_memory.py'), 'update-round',
    '--path', ioApi.join(runDir, 'round-records.json'), '--round', String(round)]
  args.push(...(inline ? ['--updates-json', updatesJson] : ['--updates-path', stagedPath]))
  args.push('--updates-hash', ioApi.contentHash(updatesJson),
    '--expected-hash', expectedHash || ioApi.contentHash(''), '--run-id', runId)
  if (lease) args.push('--lease', lease)
  const parsed = await _selfVerifiedHelper(ioApi, args, stagedPath, updatesJson, 'updates-corrupt')
  if (!parsed.ok) return { ok: false, reason: parsed.reason || 'helper-failed' }
  // #211: only the CAS hash rides back — the shell keeps no in-memory record copy (the durable
  // skeleton on disk is the source of truth the deciders read next round).
  return { ok: true, contentHash: parsed.contentHash }
}

async function coverageDecisionTarget(runDir, context, legKind, ioApi) {
  if (context && context.docPath) return { mode: 'doc', path: context.docPath }
  const path = (context && context.coverageDecisionPath) || (legKind && legKind.coverageDecisionPath) || ioApi.join(runDir, 'review-coverage-decisions.json')
  return { mode: 'code', path }
}

// The coverage read is computed entirely PYTHON-SIDE (coverage_decisions.py load): decisions
// parsed and the fence hash taken over the exact on-disk bytes. A raw courier readText here
// poisoned the loop live (2026-07-02, 4 runs): the sandbox io leaf answers PROSE for a
// missing/odd file, and contentHash(prose) turned every later fenced write into a permanent
// 'stale' park — courier text must never enter an integrity decision. A mangled helper
// ANSWER fails JSON.parse and parks fail-closed (never silently-empty decisions).
async function loadCoverageDecisions(target, ioApi) {
  const out = await ioApi.runHelper('python3', [libPath('coverage_decisions.py'), 'load',
    '--path', target.path, '--mode', target.mode === 'doc' ? 'doc' : 'code'])
  const stdout = String((out && out.stdout) || '')
  try {
    const parsed = JSON.parse(stdout)
    if (parsed && typeof parsed === 'object') return parsed
  } catch (_) { /* fall through to fail-closed */ }
  const firstBrace = stdout.indexOf('{')
  const lastBrace = stdout.lastIndexOf('}')
  if (firstBrace >= 0 && lastBrace > firstBrace) {
    try {
      const parsed = JSON.parse(stdout.slice(firstBrace, lastBrace + 1))
      if (parsed && typeof parsed === 'object') return parsed
    } catch (_) { /* fall through to fail-closed */ }
  }
  return { ok: false, state: 'unreadable', reason: 'coverage-load-helper-failed' }
}

function collectRoundUsage(roundFindings, round, synthesized) {
  const usage = {}
  for (const [name, result] of Object.entries(roundFindings || {})) {
    const real = _realUsage(result && result.usage)
    if (real) usage[`${name}:r${round}`] = real
  }
  const synthUsage = _realUsage(synthesized && synthesized.usage)
  if (synthUsage) usage[`synthesis:r${round}`] = synthUsage
  return usage
}

function _realUsage(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  const out = {}
  let positive = false
  for (const [key, v] of Object.entries(value)) {
    if (typeof v !== 'number' || !Number.isFinite(v)) continue
    if (v > 0) positive = true
    out[key] = v
  }
  return positive ? out : null
}

function _stripZeroUsage(out) {
  if (!out || typeof out !== 'object' || Array.isArray(out)) return out
  const usage = _realUsage(out.usage)
  if (usage) return Object.assign({}, out, { usage })
  if (!Object.prototype.hasOwnProperty.call(out, 'usage')) return out
  const cleaned = Object.assign({}, out)
  delete cleaned.usage
  return cleaned
}

function _expectedReceiptIds(opts) {
  opts = opts || {}
  if (Array.isArray(opts.receiptCoverageDecisionIds)) return opts.receiptCoverageDecisionIds.filter(Boolean)
  return (opts.coverageDecisions || []).map((d) => d && d.id).filter(Boolean)
}

function _reviewerReceiptIssue(result, opts) {
  if (!result || result.confidence !== 'high' || result.externalReview) return null
  const receipt = result.verificationReceipt
  if (!receipt || typeof receipt !== 'object' || Array.isArray(receipt)) return 'missing'
  if (opts && opts.receiptArtifact && receipt.artifact !== opts.receiptArtifact) return 'stale'
  if (!Array.isArray(receipt.coverageDecisionIds)) return 'stale'
  const gotIds = new Set(receipt.coverageDecisionIds || [])
  for (const id of _expectedReceiptIds(opts)) if (!gotIds.has(id)) return 'stale'
  const neededSteps = new Set(['citation', 'reachability', 'missing-check', 'tooling'])
  for (const step of Array.isArray(receipt.chain) ? receipt.chain : []) {
    if (step && typeof step === 'object' && step.evidence) neededSteps.delete(step.step)
  }
  return neededSteps.size ? 'stale' : null
}

function _withReceiptFreshness(shaped, opts) {
  if (!shaped || !Array.isArray(shaped.findings) || shaped.confidence !== 'high' || shaped.externalReview) return shaped
  const issue = _reviewerReceiptIssue(shaped, opts || {})
  if (!issue) return shaped
  const out = Object.assign({}, shaped, { confidence: 'low' })
  if (issue === 'missing') out.receiptMissing = true
  else {
    out.receiptStale = true
    out.findings = []
  }
  return out
}

function _retryableReviewerIssue(out) {
  return !_validReviewerResult(out) || !!(out && (out.receiptMissing || out.receiptStale))
}

// #212: a retry that exists to cure a SPECIFIC defect must say which one, so reviewerAgent can add a
// corrective instruction (a blind re-dispatch of the identical prompt just re-flips the same coin).
// Covers every retryable cause, not only receipts: `malformed` catches a schema-failing/off-task
// answer (live precedent: a reviewer glitched onto an unrelated MCP connector and returned nonsense).
function _retryReason(out) {
  if (out && out.receiptMissing) return 'receipt-missing'
  if (out && out.receiptStale) return 'receipt-stale'
  if (!_validReviewerResult(out)) return 'malformed'
  return null
}

function expectedUsageLeaves(reviewerSet, round, legKind, fixRan) {
  const leaves = (reviewerSet || []).map((name) => `${name}:r${round}`)
  if (legKind && legKind.panel) leaves.push(`synthesis:r${round}`)
  if (legKind && legKind.code) leaves.push(`verify:r${round}`)
  if (fixRan) leaves.push(`fix:r${round}`)
  return leaves
}

// The telemetry round scalars (roundCount, dimensionCounts) come from round-records.json ON
// DISK (review_telemetry.py write-from-records composes Python-side); only small scalars ride
// the invocation, and the helper answers with the same small summary it wrote (D3: telemetry
// never embeds rounds) so finalizeVerdict never re-reads the file back through the pipe.
// No expected-hash: the telemetry file is a single-writer run artifact written once at the
// terminal — the old pre-read + CAS pair cost a leaf and protected nothing the lease doesn't.
async function writeTelemetry(runDir, expectedLeaves, usage, terminal, runId, lease, ioApi) {
  const args = [libPath('review_telemetry.py'), 'write-from-records',
    '--path', ioApi.join(runDir, 'review-telemetry.json'),
    '--records-path', ioApi.join(runDir, 'round-records.json'),
    '--expected-leaves-json', JSON.stringify(expectedLeaves || []),
    '--usage-json', JSON.stringify(usage || {}),
    '--run-id', runId]
  if (terminal) args.push('--terminal', String(terminal))
  if (lease) args.push('--lease', lease)
  const out = await ioApi.runHelper('python3', args)
  try {
    return out.ok ? JSON.parse(out.stdout) : { ok: false, benchmarkValid: false, reason: 'telemetry-write-failed' }
  } catch (_) {
    return { ok: false, benchmarkValid: false, reason: 'telemetry-write-failed' }
  }
}

async function recordCoverageDecision(targetPath, decision, expectedHash, mode, runId, lease, ioApi) {
  const cmd = mode === 'code' ? 'record-code' : 'record-doc'
  const args = [libPath('coverage_decisions.py'), cmd, '--path', targetPath, '--decision-json', JSON.stringify(decision), '--expected-hash', expectedHash, '--run-id', runId]
  if (lease) args.push('--lease', lease)
  const out = await ioApi.runHelper('python3', args)
  try {
    return out.ok ? JSON.parse(out.stdout) : { ok: false, reason: 'coverage-decision-write-failed' }
  } catch (_) {
    return { ok: false, reason: 'coverage-decision-write-failed' }
  }
}

// gatherReviewSetup: fold 2 (#141) — run the review loop's decision-free entry stretch (run-dir
// mkdir + deferred-set seed read + entry-bootstrap + coverage load) as ONE review_setup_gather.py leaf,
// all Python-side. Returns the combined blob { ok, memory, deferredSet, coverage } for the caller to
// hand reviewPanel as `preloaded` (and, on the doc leg, to seed runtimeDeferred). Returns null on a
// gather transport failure — the caller then falls back to a plain mkdir + reviewPanel's own reads
// (correct, just unfolded). reviewerSet MUST equal the set the caller passes reviewPanel, so the
// gathered memory/coverage are byte-parity with reviewPanel's own entry reads.
async function gatherReviewSetup({ runDir, reviewerSet, context, legKind, ioApi }) {
  const api = ioApi || io()
  const target = await coverageDecisionTarget(runDir, context, legKind || {}, api)
  const args = [libPath('review_setup_gather.py'), 'gather',
    '--run-dir', runDir,
    '--records-path', api.join(runDir, 'round-records.json'),
    '--dimensions', JSON.stringify(reviewerSet || []),
    '--extras-path', api.join(runDir, 'last-extras.json'),
    '--deferred-path', api.join(runDir, 'deferred-set.json'),
    '--coverage-path', target.path,
    '--coverage-mode', target.mode === 'doc' ? 'doc' : 'code',
    '--out-path', api.join(runDir, 'review-setup-gather.json'),
    '--receipt-threshold', String(_SUMMARY_RECEIPT_BOUND)]
  const out = await api.runHelper('python3', args, { payload: true })
  let parsed = _jsonFromStdout(out)
  if (parsed && parsed.receipt === 'review-setup-gather') {
    const read = await _readReceiptText(api, parsed, 'review-setup-gather', 'review-setup-gather-unreadable')
    if (!read.ok) return null
    try { parsed = JSON.parse(read.text) } catch (_) { parsed = null }
  }
  if (parsed && parsed.ok && parsed.resume && parsed.coverage) {
    if (!parsed.deferredSet || typeof parsed.deferredSet !== 'object') parsed.deferredSet = {}
    return parsed
  }
  return null
}

async function reviewPanel({ reviewerSet, context, rubric, runKey, runDir, fixStep,
                            maxRounds = 7, legKind = {}, verifyCommand = 'none',
                            forceCoverageDecisionExpectedHash, preloaded }) {
  runDir = runDir || runKey
  const runId = runKey || runDir
  const lease = legKind && legKind.lease
  const ioApi = io()
  // #211: the entry read rides DECISIONS, not records. The doc/code leg hands us a PRELOADED gather
  // (resume decision + round-1 plan + coverage + deferred, folded into ONE leaf); standalone (the
  // smokes) we self-gather. The shell holds NO findings — only decisions + the CAS hash. One retry,
  // then a mangled/unreadable entry parks cannot-certify (never a fresh round on an unverifiable seed).
  let setup = (preloaded && preloaded.resume) ? preloaded
    : await gatherReviewSetup({ runDir, reviewerSet: reviewerSet || [], context, legKind, ioApi })
  if (!setup || !setup.resume) {
    setup = await gatherReviewSetup({ runDir, reviewerSet: reviewerSet || [], context, legKind, ioApi })
  }
  const resume = setup && setup.resume
  let round = (resume && resume.round) || 1
  const allUsage = {}
  let fixRanThisRun = false
  if (!resume || !resume.ok) {
    // a stable machine-readable park reason (round-memory-<state>), never a raw loader exception —
    // a mangled gather (resume null) is 'round-memory-unreadable', a corrupt file 'round-memory-corrupt'.
    const reason = (resume && resume.state) ? 'round-memory-' + resume.state
      : 'round-memory-unreadable'
    return await finalizeVerdict(
      { schemaVersion: SCHEMA_VERSION, terminal: 'cannot-certify', reason, round },
      reviewerSet, round, legKind, fixRanThisRun, allUsage, runDir, runId, lease, ioApi)
  }
  let memoryContentHash = resume.contentHash
  let lastExtras = resume.extras !== undefined ? resume.extras : null
  let entryPlan = setup.plan || null
  let entryCoverage = setup.coverage || null
  let justMarkedForConfirmation = false

  if (!reviewerSet || reviewerSet.length === 0) {
    const v = await tallyRound({ runDir, round, roster: reviewerSet || [], maxRounds,
                                   roundFindings: {}, legKind, verifyResult: null,
                                   policy: { roundKind: 'baseline' }, coverageDecisions: [],
                                   coverageTarget: null, runId, extras: lastExtras, ioApi })
    return _usable(v) ? await finalizeVerdict(v, reviewerSet, round, legKind, fixRanThisRun, allUsage, runDir, runId, lease, ioApi) : _failClosed()
  }

  while (true) {
    const coverageTarget = await coverageDecisionTarget(runDir, context, legKind, ioApi)
    // The PLAN decision (schedule + carried + enterConfirmation) and the per-round coverage read.
    // Round 1: both came from the entry gather (consume once). Later rounds: the plan-round decider
    // with the coverage read FOLDED in (one round-entry leaf, #118). A mangled plan answer parks.
    let plan, coverageState
    if (entryPlan) {
      plan = entryPlan; entryPlan = null
      coverageState = entryCoverage; entryCoverage = null
    } else {
      plan = await planRoundDecider({ runDir, round, roster: reviewerSet,
        changedSubjects: (lastExtras && lastExtras.changedSubjects),
        justMarked: justMarkedForConfirmation, coverageTarget, ioApi })
      if (!plan) {
        return await finalizeVerdict(
          { schemaVersion: SCHEMA_VERSION, terminal: 'cannot-certify', reason: 'round-plan-unreadable', round },
          reviewerSet, round, legKind, fixRanThisRun, allUsage, runDir, runId, lease, ioApi)
      }
      coverageState = plan.coverage || null
    }
    justMarkedForConfirmation = false
    if (!coverageState || !coverageState.ok) {
      return await finalizeVerdict(
        { schemaVersion: SCHEMA_VERSION, terminal: 'cannot-certify', reason: 'coverage-decisions-' + ((coverageState && (coverageState.state || coverageState.reason)) || 'unreadable'), round },
        reviewerSet, round, legKind, fixRanThisRun, allUsage, runDir, runId, lease, ioApi)
    }
    const coverageDecisions = coverageState.decisions
    let coverageContentHash = coverageState.contentHash
    const enterConfirmation = !!plan.enterConfirmation
    const roundKind = plan.roundKind

    // #174 confirmation coverage-marker check: every coverage id the latest record marked (the plan
    // decider surfaces them from disk) must still be visible in the live coverage — a decision lost
    // between marking and confirmation parks rather than certifies over a missing principle.
    if (enterConfirmation && Array.isArray(plan.latestCoverageDecisionIds) && plan.latestCoverageDecisionIds.length) {
      const visible = new Set(coverageDecisions.map((d) => d.id))
      if (plan.latestCoverageDecisionIds.some((id) => !visible.has(id))) {
        return await finalizeVerdict(
          { schemaVersion: SCHEMA_VERSION, terminal: 'cannot-certify', reason: 'coverage-decision-marker-missing', round },
          reviewerSet, round, legKind, fixRanThisRun, allUsage, runDir, runId, lease, ioApi)
      }
    }

    const scheduled = plan.dimensions || {}
    const roundFindings = {}
    const receiptContext = { artifact: runId + ':round-' + round, coverageDecisionIds: coverageDecisions.map((d) => d.id).filter(Boolean) }
    await parallel(reviewerSet
      .filter((r) => (scheduled[r] || {}).action !== 'skip')
      .map((r) => () => dispatchReviewer(r, reviewerContext(context, coverageDecisions, receiptContext), rubric, runDir, round, roundFindings, Object.assign({}, scheduled[r], { roundKind, coverageDecisions, receiptContext, receiptArtifact: receiptContext.artifact }))))
    for (const [name, sched] of Object.entries(scheduled)) {
      // the carried (skipped-dimension) state comes from the plan decider (structurally clean —
      // findings empty by construction); a defensive fallback covers a missing carried entry.
      if (sched.action === 'skip') roundFindings[name] = (plan.carried && plan.carried[name]) ||
        { status: 'skipped', findings: [], confidence: 'low', carriedFromRound: sched && sched.carriedFromRound }
    }

    let synthesized = null
    if (legKind.panel) {
      try {
        synthesized = await synthesizeRound(roundFindings, context, rubric, runDir, round)
      } catch (e) {
        try { log(`review-panel r${round}: synthesis threw (${e && e.message ? e.message : e}) — falling back to raw compile`) } catch (_) {}
        synthesized = null
      }
      if (!synthesized) {
        try { log(`review-panel r${round}: synthesis produced no result — falling back to raw compile (no findings dropped)`) } catch (_) {}
      }
      graftSynthesizedFindings(roundFindings, synthesized)
    }

    let verifyResult = null
    if (legKind.code) {
      try { verifyResult = await verifyAgent(verifyCommand, runDir, round, ioApi) }
      catch (e) { verifyResult = 'fail' }
    }

    const tokenUsage = collectRoundUsage(roundFindings, round, synthesized)
    Object.assign(allUsage, tokenUsage)

    const roundCoverageDecisions = annotateChallengedCoverage(coverageDecisions, roundFindings, reviewerSet)
    const record = reviewMemory.recordFromDimensionResults(round, roundKind, roundFindings, lastExtras && lastExtras.changedSubjects, roundCoverageDecisions, tokenUsage, enterConfirmation && roundKind === 'confirmation')
    // persist the SKELETON down (the verified CAS write, unchanged) — then discard it: the tally
    // decider reads the just-persisted disk state, so the shell keeps no record copy in memory.
    const persisted = await persistRoundRecord(runDir, reviewerSet, record, memoryContentHash, runId, lease, ioApi)
    if (!persisted.ok) {
      return await finalizeVerdict(
        { schemaVersion: SCHEMA_VERSION, terminal: 'cannot-certify', reason: 'round-memory-write-failed', round },
        reviewerSet, round, legKind, fixRanThisRun, allUsage, runDir, runId, lease, ioApi)
    }
    memoryContentHash = persisted.contentHash

    // the tally reads the just-persisted rounds from disk (breaker + terminal + confirmation
    // economics + certification) and, on a continue, writes the fixer worklist to the SAME leaf and
    // rides only its pointer back. gate / present-blocking / uncertified-reason ride DOWN (below).
    const verdict = await tallyRound({ runDir, round, roster: reviewerSet, maxRounds,
      roundFindings, legKind, synthesized, verifyResult, policy: { roundKind }, coverageDecisions: roundCoverageDecisions,
      coverageTarget, runId, extras: lastExtras, enterConfirmation, ioApi })
    if (!_usable(verdict)) return _failClosed()

    if (verdict.terminal !== 'continue') {
      return await finalizeVerdict(verdict, reviewerSet, round, legKind, fixRanThisRun, allUsage, runDir, runId, lease, ioApi)
    }

    if (verdict.reason === 'awaiting final confirmation round') {
      round += 1
      continue
    }

    fixRanThisRun = true
    // #211 pointers-down: the fixer receives the worklist PATH (the tally leaf wrote it), never
    // inlined findings. A continue with no worklist pointer means the fold write failed — park.
    const worklistPath = verdict.worklistPath
    if (!worklistPath) {
      return await finalizeVerdict(
        { schemaVersion: SCHEMA_VERSION, terminal: 'cannot-certify', reason: 'fix-context-' + (verdict.worklistReason || 'write-failed'), round },
        reviewerSet, round, legKind, fixRanThisRun, allUsage, runDir, runId, lease, ioApi)
    }
    const fixResult = await runFixStep(fixStep, { worklistPath, round }, verdict, runDir)
    if (!fixResult.ok) {
      const failVerdict = await tallyRound({ runDir, round, roster: reviewerSet, maxRounds,
        roundFindings, legKind, synthesized, verifyResult, policy: { roundKind }, coverageDecisions: roundCoverageDecisions,
        coverageTarget, runId, extras: fixResult.extras || lastExtras, fixStatus: 'failed', enterConfirmation, ioApi })
      return await finalizeVerdict(
        _usable(failVerdict) ? failVerdict : _failClosed(),
        reviewerSet, round, legKind, fixRanThisRun, allUsage, runDir, runId, lease, ioApi)
    }

    lastExtras = fixResult.extras || { changedSubjects: (fixResult.fixResult && fixResult.fixResult.changedSubjects) || [], needsConfirmation: true }
    let recordedCoverageDecisions = coverageDecisions
    let expectedCovHash = forceCoverageDecisionExpectedHash || coverageContentHash
    for (const decision of ((fixResult.fixResult && fixResult.fixResult.coverageDecisions) || [])) {
      const target = await coverageDecisionTarget(runDir, context, legKind, ioApi)
      const res = await recordCoverageDecision(target.path, decision, expectedCovHash, target.mode, runId, lease, ioApi)
      if (!res.ok) {
        return await finalizeVerdict(
          { schemaVersion: SCHEMA_VERSION, terminal: 'cannot-certify', reason: 'coverage-decision-write-failed', round },
          reviewerSet, round, legKind, fixRanThisRun, allUsage, runDir, runId, lease, ioApi)
      }
      const reloaded = await loadCoverageDecisions(target, ioApi)
      if (!reloaded.ok) {
        return await finalizeVerdict(
          { schemaVersion: SCHEMA_VERSION, terminal: 'cannot-certify', reason: 'coverage-decisions-' + (reloaded.state || 'unreadable'), round },
          reviewerSet, round, legKind, fixRanThisRun, allUsage, runDir, runId, lease, ioApi)
      }
      recordedCoverageDecisions = reloaded.decisions
      expectedCovHash = reloaded.contentHash
      coverageContentHash = reloaded.contentHash
    }

    // body dump BEFORE the post-fix persist: both must happen, the dump is best-effort
    // anyway, and this ordering shrinks the crash window in which the audit bodies are
    // lost while the delta survives (or vice versa) at zero protocol cost.
    await dumpRoundBodiesBestEffort(runDir, round, verdict, fixResult.fixResult || {}, ioApi)
    const postFix = await persistPostFixRecord(runDir, reviewerSet, round, fixResult.fixResult || {}, recordedCoverageDecisions, memoryContentHash, runId, lease, ioApi, legKind)
    if (!postFix.ok) {
      return await finalizeVerdict(
        { schemaVersion: SCHEMA_VERSION, terminal: 'cannot-certify', reason: 'round-memory-write-failed', round },
        reviewerSet, round, legKind, fixRanThisRun, allUsage, runDir, runId, lease, ioApi)
    }
    memoryContentHash = postFix.contentHash
    justMarkedForConfirmation = true
    try { await ioApi.writeFile(`${runDir}/last-extras.json`, JSON.stringify(lastExtras)) } catch (_) {}
    round += 1
  }
}

async function finalizeVerdict(verdict, reviewerSet, round, legKind, fixRan, allUsage, runDir, runId, lease, ioApi) {
  const expectedLeaves = []
  for (let r = 1; r <= round; r += 1) expectedLeaves.push(...expectedUsageLeaves(reviewerSet, r, legKind, fixRan && r === round))
  const telemWrite = await writeTelemetry(runDir, expectedLeaves, allUsage, verdict.terminal, runId, lease, ioApi)
  // Attach the SMALL summary the helper answered with (the round history stays in
  // round-records.json only) — re-reading the telemetry file back through the pipe would
  // re-create the mega-payload hop, and a verdict embedding every round would ride the
  // terminal-record write the same way.
  let telemetry = { benchmarkValid: false, reason: 'telemetry-write-failed' }
  if (telemWrite.ok) {
    telemetry = Object.assign({}, telemWrite)
    delete telemetry.ok
  }
  return Object.assign({}, verdict, { telemetry })
}

function _validReviewerResult(out) {
  return !!out && Array.isArray(out.findings) && (out.confidence === 'high' || out.confidence === 'low')
}

function normalizeReviewerFindings(findings) {
  return (findings || []).map((finding) => {
    if (!finding || typeof finding !== 'object' || Array.isArray(finding)) return finding
    if ((finding.title === undefined || finding.title === null || finding.title === '') &&
        typeof finding.summary === 'string' && finding.summary) {
      return Object.assign({}, finding, { title: finding.summary })
    }
    return finding
  })
}

function _shapeReviewerResult(out, opts) {
  if (Array.isArray(out)) {
    const conf = ((opts || {}).tier === 'reviewer' && out.length > 0) ? 'low' : 'high'
    return { findings: normalizeReviewerFindings(out), confidence: conf, legacyArray: true }
  }
  const shaped = _stripZeroUsage(out)
  if (!shaped || !Array.isArray(shaped.findings)) return shaped
  return _withReceiptFreshness(Object.assign({}, shaped, { findings: normalizeReviewerFindings(shaped.findings) }), opts || {})
}

async function dispatchReviewer(reviewer, context, rubric, runDir, round, roundFindings, opts) {
  const baseOpts = opts || {}
  let out = _shapeReviewerResult(await reviewerAgent(reviewer, context, rubric, runDir, round, baseOpts), baseOpts)
  let escalated = false
  if (baseOpts.tier === 'reviewer' && (_retryableReviewerIssue(out) || out.confidence !== 'high')) {
    escalated = true
    // #212: the escalation to reviewer-deep IS a re-dispatch — carry the corrective retryReason when
    // the shallow answer had a curable defect (null when it was just an honest low, nothing to correct).
    const deepOpts = Object.assign({}, baseOpts, { tier: 'reviewer-deep', escalatedFrom: 'reviewer', retryReason: _retryReason(out) })
    out = _shapeReviewerResult(await reviewerAgent(reviewer, context, rubric, runDir, round, deepOpts), deepOpts)
    if (_retryableReviewerIssue(out)) {
      out = _shapeReviewerResult(await reviewerAgent(reviewer, context, rubric, runDir, round, Object.assign({}, deepOpts, { retryFrom: 'reviewer-deep', retryReason: _retryReason(out) })), deepOpts)
    }
  } else if (baseOpts.tier === 'reviewer-deep' && _retryableReviewerIssue(out)) {
    out = _shapeReviewerResult(await reviewerAgent(reviewer, context, rubric, runDir, round, Object.assign({}, baseOpts, { tier: 'reviewer-deep', retryFrom: 'reviewer-deep', retryReason: _retryReason(out) })), baseOpts)
  }
  if (!_validReviewerResult(out)) {
    roundFindings[reviewer] = { status: 'missing', dimension: reviewer, findings: [], confidence: 'low', malformed: true, legacyArray: !!(out && out.legacyArray), escalated }
    return
  }
  roundFindings[reviewer] = Object.assign({ status: 'run', dimension: reviewer, escalated, tier: baseOpts.tier, malformed: false }, out)
}

async function synthesizeRound(roundFindings, context, rubric, runDir, round) {
  const compiled = panelTally.compileDimensionResults(roundFindings)
  const leaf = await synthesisLeaf(compiled, context, rubric, runDir, round)
  const consumed = loopSynthesis.consume(compiled, leaf && Array.isArray(leaf.verdicts) ? leaf.verdicts : [])
  return Object.assign(consumed, { usage: leaf && leaf.usage })
}

function graftSynthesizedFindings(roundFindings, synthesized) {
  if (!synthesized || typeof synthesized !== 'object' || !Array.isArray(synthesized.findings)) return
  const keptById = Object.create(null)
  for (const kept of synthesized.findings) {
    if (!kept || typeof kept !== 'object' || Array.isArray(kept)) continue
    keptById[circuitBreaker.findingIdentity(kept)] = kept
  }
  for (const [name, result] of Object.entries(roundFindings || {})) {
    if (!result || typeof result !== 'object' || !Array.isArray(result.findings)) continue
    const findings = []
    for (const finding of result.findings) {
      if (!finding || typeof finding !== 'object' || Array.isArray(finding)) continue
      const kept = keptById[circuitBreaker.findingIdentity(finding)]
      if (!kept) {
        if (finding.file === null || finding.file === undefined || finding.line === null || finding.line === undefined) {
          // synthesis could not verify this no-location finding (no keep verdict) but we keep it so
          // it still counts for the gate. Flag it `synthesisUnverified` so the tally decider can
          // reproduce the OLD `compiled` view: the CURRENT round's breaker findings + present-deferred
          // EXCLUDE it (synthesis dropped it), while recurrence/generalize over prior rounds still
          // see it (#211 parity — this preserves the #174 generalize-grace, which relied on exactly
          // this current=compiled / prior=record asymmetry).
          findings.push(Object.assign({}, finding, { synthesisUnverified: true }))
        }
        continue
      }
      const enriched = Object.assign({}, finding)
      if ((enriched.title === undefined || enriched.title === null || enriched.title === '') &&
          kept.title !== undefined && kept.title !== null && kept.title !== '') {
        enriched.title = kept.title
      }
      if (kept.severity !== undefined && kept.severity !== null && kept.severity !== '') enriched.severity = kept.severity
      if (!enriched.classKey && kept.classKey) enriched.classKey = kept.classKey
      findings.push(enriched)
    }
    roundFindings[name] = Object.assign({}, result, { findings })
  }
}

async function verifyAgent(verifyCommand, runDir, round, ioApi) {
  // dumb pipe (run verify_gate.py, echo its JSON): courier:true so the bundle preamble pins it to
  // the cheapest model unconditionally (#118 — an unmarked label like 'run verify' inherits the
  // session model). The preamble strips the marker before the real agent().
  ioApi = ioApi || io()
  const outPath = ioApi.join(runDir, `verify-result-r${round}.json`)
  const command = `python3 ${libPath('verify_gate.py')} --command ${shq(verifyCommand || 'none')} --out ${shq(outPath)}`
  const prompt =
    `Run exactly this command with Bash and return ONLY its final stdout JSON, unchanged.\n` +
    `This command can run for several minutes. Invoke Bash with an explicit timeout parameter of 600000 ms ` +
    `(the Bash tool accepts a timeout parameter up to 600000 ms). Do NOT background it. ` +
    `Do NOT answer until the command prints its final JSON. Your structured output fields must be the JSON object's own fields ` +
    `(result/code/tail); do not nest the JSON as a string.\n\n` +
    command
  const runCourier = () => agent(prompt, { label: 'run verify', schema: VERIFY_SCHEMA, courier: true })
  // A THROWN verify courier must be treated EXACTLY like an unusable answer — never collapsed to 'fail'
  // before the file read-back runs. Live (harness-run 26, wf_1ed21465-6f3): the haiku courier ran
  // verify_gate.py correctly (round-stamped file written, result PASS) but never called its
  // StructuredOutput tool (emitted the tag as literal text), so agent() THREW; the call-site catch
  // then collapsed a clean round to 'fail' with the pass evidence sitting on disk. Swallowing the throw
  // to null here keeps the round-stamped file authoritative in BOTH directions: it is still REQUIRED to
  // grant pass (anti-fabrication, unchanged) AND is now consulted before we ever conclude fail. The
  // call-site catch remains only as a last-resort backstop.
  const tryCourier = async () => { try { return await runCourier() } catch (_) { return null } }
  const out = await tryCourier()
  const commandSkipped = !verifyCommand || String(verifyCommand).trim().toLowerCase() === 'none'
  if (commandSkipped) return verifyResultFromPayload(verifyCommand, out, { allowPass: false }) || 'fail'
  const readBack = await ioApi.readJson(outPath, null)
  const fromFile = verifyResultFromPayload(verifyCommand, readBack, { allowPass: true })
  if (fromFile) return fromFile
  const fromDirect = verifyResultFromPayload(verifyCommand, out, { allowPass: false })
  if (fromDirect) return fromDirect
  const retryOut = await tryCourier()
  const retryReadBack = await ioApi.readJson(outPath, null)
  const fromRetryFile = verifyResultFromPayload(verifyCommand, retryReadBack, { allowPass: true })
  if (fromRetryFile) return fromRetryFile
  // Both couriers AND both read-backs yielded nothing usable -> the anti-fabrication fail-closed default.
  return verifyResultFromPayload(verifyCommand, retryOut, { allowPass: false }) || 'fail'
}

function own(obj, key) {
  return !!obj && Object.prototype.hasOwnProperty.call(obj, key)
}

function _integerString(value) {
  const s = String(value).trim()
  return /^-?\d+$/.test(s) ? s : null
}

function verifyResultFromPayload(verifyCommand, payload, opts) {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) return null
  opts = opts || {}
  if (typeof payload.result === 'string') {
    try {
      const nested = JSON.parse(payload.result)
      if (nested && typeof nested === 'object' && !Array.isArray(nested)) {
        return verifyResultFromPayload(verifyCommand, nested, opts)
      }
    } catch (_) { /* fall through to normal result handling */ }
  }
  const command = verifyCommand || (own(payload, 'command') ? payload.command : 'none')
  const commandSkipped = !command || String(command).trim().toLowerCase() === 'none'
  if (payload.result === 'pass') return opts.allowPass ? 'pass' : null
  if (payload.result === 'skipped') return commandSkipped ? 'skipped' : null
  if (payload.result === 'fail' || payload.result === 'timeout') return payload.result
  if (commandSkipped) return 'skipped'
  const timedOut = payload.timedOut === true || String(payload.timedOut).toLowerCase() === 'true'
  if (timedOut) return 'timeout'
  const rc = own(payload, 'returncode') ? payload.returncode : (own(payload, 'code') ? payload.code : undefined)
  const rcStr = _integerString(rc)
  if (!rcStr) return null
  const classified = verifyGateTwin.classify({ command, returncode: rcStr, timedOut: false })
  return classified === 'pass' && !opts.allowPass ? null : classified
}

// The LIVE tally: compute the answer-time facts from the round's own reviewer answers, ride the
// scalars the durable skeleton can't hold DOWN to the tally-round decider (which owns the terminal
// from disk + writes the fix worklist on a continue), and assemble the verdict — this round's
// findings/drops/downgrades for the readout, the decider's decisions for control flow.
async function tallyRound({ runDir, round, roster, maxRounds, roundFindings = {},
                           legKind = {}, synthesized = null, verifyResult = null,
                           fixStatus = 'completed', extras = null, policy = {}, coverageDecisions = [],
                           coverageTarget = null, runId, enterConfirmation = false, ioApi }) {
  const api = ioApi || io()
  const safeExtras = {}
  if (extras && typeof extras === 'object') {
    for (const k of ['fixes', 'deferred', 'parentOrigin']) if (k in extras) safeExtras[k] = extras[k]
  }
  try {
    if (!roster || roster.length === 0) {
      return Object.assign({ schemaVersion: SCHEMA_VERSION, gate: 'cannot-certify', confidence: 'low',
        findings: [], missing: [], drops: [], downgrades: [], terminal: 'cannot-certify', round,
        reason: 'empty reviewer set — nothing to certify' }, safeExtras)
    }
    // answer-time facts from the LIVE reviewer answers (the durable skeleton strips the receipts
    // these need): gate/confidence/missing, present-blocking, and the #212 named uncertified reason.
    const receiptContext = { artifact: runId + ':round-' + round, coverageDecisionIds: (coverageDecisions || []).map((d) => d.id).filter(Boolean) }
    const gateOut = panelTally.roundGateFromDimensionResults(
      roundFindings, roster, policy.roundKind === 'confirmation', receiptContext)
    const gate = gateOut.gate
    const confidence = gateOut.confidence
    const missing = gateOut.incomplete
    let compiled, drops, downgrades
    if (synthesized && typeof synthesized === 'object') {
      compiled = synthesized.findings || []
      drops = synthesized.drops || []
      // #186: blocking→non-blocking severity downgrades ride alongside drops for the readout's
      // owner-scrutiny section (visibility only; the severity change itself already applied).
      downgrades = synthesized.downgrades || []
    } else {
      compiled = panelTally.compileDimensionResults(roundFindings)
      drops = []
      downgrades = []
    }
    const presentBlocking = panelTally.presentBlockingFromDimensionResults(roundFindings)
    // #212 named reason only matters on a cannot-certify GATE — compute it from the live per-seat
    // results and ride it DOWN (the decider can't recompute it: the skeleton strips the receipts).
    const uncertifiedReason = (gate === 'cannot-certify') ? panelTally.uncertifiedReason(roundFindings, roster) : null

    // the decider owns the terminal (breaker + decideTerminal + #174 economics + certification) from
    // disk; on a continue it writes the fixer worklist to the SAME leaf and rides only its pointer.
    const decided = await tallyRoundDecider({ runDir, round, roster, maxRounds, gate, confidence, missing,
      presentBlocking, uncertifiedReason, fixStatus, verifyResult, enterConfirmation, coverageTarget,
      worklistOutPath: api.join(runDir, `fix-context-r${round}.json`), ioApi: api })
    // a mangled/unparseable decider answer fails closed — never a silent clean (the #211 adversarial
    // invariant): the shell's _failClosed sentinel halts + flags recordMissing.
    if (!decided || typeof decided.terminal !== 'string') return _failClosed()

    const verdictOut = Object.assign({ schemaVersion: SCHEMA_VERSION, gate, confidence, findings: compiled,
      missing, drops, downgrades, terminal: decided.terminal, reason: decided.reason, round }, safeExtras)
    // #212 uncertified flag (from the decider — set on a cannot-certify gate, even routing to fix).
    if (decided.uncertified) verdictOut.uncertified = true
    // #174 req 4 honest certification summary rides on a certifying terminal (from the decider).
    if (decided.certification) verdictOut.certification = decided.certification
    // #211 fix-context pointer (written by the folded decider on a continue) — never inlined findings.
    if (own(decided, 'worklistPath')) verdictOut.worklistPath = decided.worklistPath
    if (own(decided, 'worklistReason')) verdictOut.worklistReason = decided.worklistReason
    return verdictOut
  } catch (exc) {
    return Object.assign({ schemaVersion: SCHEMA_VERSION, gate: 'cannot-certify', confidence: 'low',
      findings: [], missing: [], drops: [], downgrades: [], terminal: 'halted', round,
      reason: 'tally failed: ' + (exc && exc.message ? exc.message : exc) }, safeExtras)
  }
}

async function runFixStep(fixStep, fixContext, verdict, runDir) {
  try {
    const fixResult = await fixStep(fixContext, verdict, runDir)
    if (!fixResult) return { ok: false, extras: null, fixResult: null }
    const schedulingExtras = fixSchedulingExtras(fixResult)
    await recordDeferred(fixResult, verdict, runDir)
    const detailExtras = plainExtras(fixResult.extras)
    const extras = Object.assign({}, detailExtras || {}, schedulingExtras || {})
    return { ok: true, extras: Object.keys(extras).length ? extras : null, fixResult }
  } catch (e) {
    try { log(`review-panel: fix step failed, treating as fix failure -> halted: ${e && e.message ? e.message : e}`) } catch (_) {}
    return { ok: false, extras: null, fixResult: null }
  }
}

function plainExtras(value) {
  return (value && typeof value === 'object' && !Array.isArray(value)) ? value : null
}

function fixSchedulingExtras(fixResult) {
  if (!fixResult || typeof fixResult !== 'object' || Array.isArray(fixResult)) return null
  const out = {}
  if (Array.isArray(fixResult.changedSubjects)) {
    out.changedSubjects = fixResult.changedSubjects.filter((s) => POLICY_SUBJECTS.has(s))
    out.needsConfirmation = true
  }
  if (Array.isArray(fixResult.changedSubjectDetails)) out.changedSubjectDetails = fixResult.changedSubjectDetails
  else if (Array.isArray(fixResult.changedSubjects)) out.changedSubjectDetails = fixResult.changedSubjects
  const extras = plainExtras(fixResult.extras)
  if (extras && Object.prototype.hasOwnProperty.call(extras, 'needsConfirmation')) {
    out.needsConfirmation = extras.needsConfirmation
  }
  return Object.keys(out).length ? out : null
}

const VERDICT_SCHEMA = {
  type: 'object',
  required: ['terminal'],
  properties: {
    schemaVersion: { type: 'number' },
    gate: { enum: ['clean', 'blocking', 'cannot-certify'] },
    confidence: { enum: ['high', 'low'] },
    findings: { type: 'array' },
    drops: { type: 'array' },
    downgrades: { type: 'array' },
    terminal: { enum: ['continue', 'clean', 'clean-with-skips', 'cannot-certify', 'halted'] },
    reason: { type: 'string' },
    recordMissing: { type: 'boolean' },
    uncertified: { type: 'boolean' },
  },
}
const SYNTH_SCHEMA = { type: 'object', required: ['findings', 'drops'],
  properties: { findings: { type: 'array' }, drops: { type: 'array' } } }
const VERIFY_SCHEMA = { type: 'object', required: ['result'],
  properties: { result: {}, code: {}, tail: {}, command: {}, returncode: {}, timedOut: {} } }

function shq(s) { return "'" + String(s).replace(/'/g, "'\\''") + "'" }

module.exports = { reviewPanel, gatherReviewSetup, VERDICT_SCHEMA, SYNTH_SCHEMA, VERIFY_SCHEMA }

};

// ===== courier_exec.js =====
__modules["courier_exec"] = function (module, exports, require) {
let injectedAgent = null

class CourierTransportError extends Error {
  constructor(label, reason) {
    super(`courier transport failed after retry (${label}): ${reason}`)
    this.label = label
    this.reason = reason
  }
}

function setCourierAgent(fn) { injectedAgent = fn }

function currentAgent() {
  if (injectedAgent) return injectedAgent
  const root = typeof globalThis !== 'undefined' ? globalThis : undefined
  if (root && typeof root.agent === 'function') return root.agent
  throw new Error('courier agent unavailable')
}

// FR-5 cwd-rooting: mirror showrunner's selfContained() — when __SR_ROOT is set (throwaway/live-eval
// runs), root every courier command at the TARGET repo so git/build/docs paths resolve. The lib
// interpreter path itself comes from `${libPath(...)}` (#170: an absolute plugin-cache path in
// production, the repo-relative default in dev), so it resolves independent of this cwd.
// Already-rooted commands (a leading `cd `) are left untouched; without __SR_ROOT this is a no-op.
function rootedCommand(command) {
  const root = (typeof globalThis !== 'undefined' && globalThis.__SR_ROOT) ? String(globalThis.__SR_ROOT) : null
  if (!root) return command
  const trimmed = String(command).replace(/^\s+/, '')
  if (trimmed.startsWith('cd ')) return command
  return "cd '" + root.replace(/'/g, "'\\''") + "' && " + command
}

// promptFor: the courier command prompt. opts.strict adds an explicit no-improvising clause for
// state-changing single-command leaves (e.g. the lease release — live 2026-07-02 the park-path
// release courier freestyled unscripted Bash and manually released the lease). The lead ALWAYS
// begins 'Run exactly this command' (targetCommandPrompt keys off that prefix) and the command
// always follows the FIRST blank line unchanged, so the strict clause rides the prefix only.
function promptFor(command, opts) {
  const lead = (opts && opts.strict)
    ? 'Run exactly this command and return ONLY stdout, unchanged. Run ONLY this single command — ' +
      'do not run any other command, do not test, verify, explore, or re-run it, just execute the ' +
      'one command below and return its stdout verbatim:'
    : 'Run exactly this command and return ONLY stdout, unchanged:'
  return lead + '\n\n' + rootedCommand(command)
}

function firstResult(raw) {
  return Array.isArray(raw) ? raw[0] : raw
}

function stdoutOf(raw) {
  const row = firstResult(raw)
  if (row == null) return ''
  if (typeof row === 'string') return row
  if (typeof row.stdout === 'string') return row.stdout
  return ''
}

function commandOk(raw) {
  const row = firstResult(raw)
  return !(row && Object.prototype.hasOwnProperty.call(row, 'ok') && row.ok === false)
}

function missingRequired(value, required) {
  for (const key of required || []) {
    if (!Object.prototype.hasOwnProperty.call(value || {}, key)) return key
  }
  return null
}

// extractJson: fence-tolerant JSON extraction — the courier twin of the exec path's
// _parseExecResult (showrunner.js). A haiku courier sometimes wraps correct output in ```json
// fences or prose (observed live 2026-07-02 on 'read startup state'; both attempts failed the
// bare JSON.parse and the run parked 'unreadable'). Candidates, in order: (a) the FIRST fenced
// block anywhere (prose-prefixed fences included), (b) the whole trimmed string, (c) each
// individual line, LAST-to-first. Each candidate: direct JSON.parse, then a brace-slice from
// first '{' to last '}' (prose around a bare object). First candidate yielding an object/array
// wins; otherwise null (the caller retries fail-closed).
//
// The per-line pass (c) handles a `side-effect && save` chain whose answer is TWO top-level JSON
// objects on two lines — the set-gate line then the save line (live 2026-07-02, persistPhase
// parked review-plan on a healthy state). Neither the whole-string parse nor the first-{…-last-}
// slice can read two objects, so fall to the lines and take the LAST parseable one (the SAVE
// result — the caller's require() then validates THAT object). Ordered AFTER the whole-string
// candidates so a single (possibly pretty-printed) object/array is parsed whole and never
// mis-sliced into one of its own inner lines (e.g. a pretty-printed array's last element).
function extractJson(text) {
  const trimmed = String(text == null ? '' : text).trim()
  const candidates = []
  const fenceMatch = trimmed.match(/```(?:[a-zA-Z0-9]+)?\s*([\s\S]*?)```/)
  if (fenceMatch) candidates.push(fenceMatch[1].trim())
  candidates.push(trimmed)
  const lines = trimmed.split('\n')
  for (let i = lines.length - 1; i >= 0; i -= 1) {
    const line = lines[i].trim()
    if (line) candidates.push(line)
  }
  for (const candidate of candidates) {
    try {
      const parsed = JSON.parse(candidate)
      if (parsed !== null && typeof parsed === 'object') return parsed
    } catch (_e1) { /* try the brace-slice fallback */ }
    const first = candidate.indexOf('{')
    const last = candidate.lastIndexOf('}')
    if (first >= 0 && last > first) {
      try {
        const sliced = JSON.parse(candidate.slice(first, last + 1))
        if (sliced !== null && typeof sliced === 'object') return sliced
      } catch (_e2) { /* try the next candidate */ }
    }
  }
  return null
}

async function callOnce(label, command, promptOpts) {
  // `courier: true` marks this a dumb pipe for the bundle preamble's unconditional cheapest-model
  // pinning (same treatment as label 'exec'/'io'); the preamble strips it before the real agent().
  return currentAgent()(promptFor(command, promptOpts), { label, courier: true })
}

// badCourierAnswer: TRUE when a marker-carrying command's answer signals the shell DID NOT run.
// Single source of truth for both courier_exec and the bundle preamble (__sh / #194). Detects:
//   (a) a missing __SR_EXIT marker (bare payload / echo shape); and
//   (b) the literal unexpanded '__SR_EXIT:$?' from an echoed command (live wf_1494a8fa-e28).
// This proves marker-SHAPE, not execution. A courier simulating the full embedded failure branch
// (payload + __SR_EXIT:0, as libRootProbe now embeds) would still pass — #218 bounds that residual
// via runCourierMarked*'s 2 outer attempts × dispatchMarked's 3-dispatch retry/fallback chain.
// Do NOT add proof-of-execution here: the Workflow sandbox has no crypto/wall-clock/RNG primitives.
function badCourierAnswer(a) {
  const s = String(a == null ? '' : a)
  return s.indexOf('__SR_EXIT') < 0 || s.indexOf('__SR_EXIT:$?') >= 0
}

// markerSliceStdout: parse a leaf-bash answer (stdout + trailing __SR_EXIT:N) into {status, stdout}.
// helperResult wraps this for the bundle __runHelperCommand / stageAndRunHelper result shape.
function markerSliceStdout(s) {
  s = String(s || '')
  const re = /__SR_EXIT:(\d+)/g
  let m, last = null
  while ((m = re.exec(s)) !== null) last = m
  const status = last ? Number(last[1]) : 1
  let stdout = last ? s.slice(0, last.index) : s
  const markerTail = last ? s.slice(last.index + last[0].length) : ''
  stdout = stdout.replace(/^\s*```[a-zA-Z0-9]*\n?/, '').replace(/\n?```\s*$/, '').replace(/\n$/, '')
  if (/^\s*`/.test(stdout) && (/`\s*$/.test(stdout) || /^\s*`\s*$/.test(markerTail))) {
    stdout = stdout.replace(/^\s*`/, '').replace(/`\s*$/, '')
  }
  return { status, stdout }
}

function helperResult(s) {
  const sliced = markerSliceStdout(s)
  return { ok: sliced.status === 0, status: sliced.status, stdout: sliced.stdout, stderr: '' }
}

function markedPromptFor(command) {
  return 'Execute this exact shell command via your command tool and return ONLY its stdout, unchanged. ' +
    'Do not echo, fence, summarize, or describe the command:\n\n' + rootedCommand(command)
}

function wrapMarkedCommand(command) {
  return String(command) + ' 2>&1; echo __SR_EXIT:$?'
}

// dispatchMarked: the #194/__sh courier protocol — lean superheroes:courier agent, marker guard with
// retry + default-dispatch fallback. Shared by runCourierMarkedText/Json (#218: libRoot probe sites).
// Each outer attempt calls dispatchMarked once; dispatchMarked itself retries up to 3 dispatches
// (courier agent → courier agent → default agent) when badCourierAnswer fires — 2×3 total before
// CourierTransportError. That chain bounds residual simulation (see badCourierAnswer / libRootProbe).
async function dispatchMarked(label, markedCmd) {
  const baseOpts = { label, courier: true, agentType: 'superheroes:courier' }
  const prompt = markedPromptFor(markedCmd)
  let ans = stdoutOf(await currentAgent()(prompt, baseOpts))
  if (badCourierAnswer(ans)) {
    ans = stdoutOf(await currentAgent()(prompt, Object.assign({}, baseOpts)))
    if (badCourierAnswer(ans)) {
      const fo = Object.assign({}, baseOpts)
      delete fo.agentType
      ans = stdoutOf(await currentAgent()(prompt, fo))
    }
  }
  return ans
}

// runCourierMarkedText: dumb-pipe a shell command through the __SR_EXIT marker protocol and return
// stdout before the marker. Used by reconcile's libRoot-probed gather snapshot (#218).
async function runCourierMarkedText(label, command) {
  const markedCmd = wrapMarkedCommand(command)
  let last = 'empty stdout'
  for (let attempt = 0; attempt < 2; attempt += 1) {
    const ans = await dispatchMarked(label, markedCmd)
    if (badCourierAnswer(ans)) {
      last = 'missing execution marker'
      continue
    }
    const sliced = markerSliceStdout(ans)
    if (sliced.stdout.trim() !== '') return sliced.stdout
    last = 'empty stdout'
  }
  throw new CourierTransportError(label, last)
}

// runCourierMarkedJson: runCourierJson semantics over the __SR_EXIT marker protocol — execution is
// proven before a probe's embedded ok:false (e.g. __SR_LIBROOT_MISSING__) is accepted, so a lazy
// courier that parrots the failure branch from the prompt cannot park the run (#218).
async function runCourierMarkedJson(label, command, opts) {
  const options = opts || {}
  const markedCmd = wrapMarkedCommand(command)
  let last = 'empty stdout'
  for (let attempt = 0; attempt < 2; attempt += 1) {
    const ans = await dispatchMarked(label, markedCmd)
    if (badCourierAnswer(ans)) {
      last = 'missing execution marker'
      continue
    }
    const out = markerSliceStdout(ans).stdout
    if (out.trim() === '') {
      last = 'empty stdout'
      continue
    }
    const parsed = extractJson(out)
    if (parsed == null) {
      last = 'unparseable JSON'
      continue
    }
    if (parsed && parsed.ok === false && options.retryRealFailure === false) return parsed
    const missing = missingRequired(parsed, options.require || [])
    if (missing) {
      last = `missing required field ${missing}`
      continue
    }
    return parsed
  }
  throw new CourierTransportError(label, last)
}

// runCourierText deliberately does NOT strip fences: its payload is arbitrary text whose
// legitimate content may itself contain ``` fences — unfencing here would corrupt it. JSON
// couriers get the fence-tolerant treatment in runCourierJson (extractJson) instead.
async function runCourierText(label, command) {
  let last = 'empty stdout'
  for (let attempt = 0; attempt < 2; attempt += 1) {
    const raw = await callOnce(label, command)
    if (!commandOk(raw)) {
      return stdoutOf(raw)
    }
    const out = stdoutOf(raw)
    if (out.trim() !== '') return out
    last = 'empty stdout'
  }
  throw new CourierTransportError(label, last)
}

async function runCourierJson(label, command, opts) {
  const options = opts || {}
  const promptOpts = options.strict ? { strict: true } : undefined
  let last = 'empty stdout'
  for (let attempt = 0; attempt < 2; attempt += 1) {
    const raw = await callOnce(label, command, promptOpts)
    const out = stdoutOf(raw)
    if (!commandOk(raw)) {
      return { ok: false, error: out.trim() || 'command failed' }
    }
    if (out.trim() === '') {
      last = 'empty stdout'
      continue
    }
    const parsed = extractJson(out)   // fence-tolerant (see extractJson) — bare parse alone parked live runs
    if (parsed == null) {
      last = 'unparseable JSON'
      continue
    }
    if (parsed && parsed.ok === false && options.retryRealFailure === false) return parsed
    const missing = missingRequired(parsed, options.require || [])
    if (missing) {
      last = `missing required field ${missing}`
      continue
    }
    return parsed
  }
  throw new CourierTransportError(label, last)
}

async function runCourierBatchJson(label, commands, opts) {
  const joined = commands.join('\n')
  const parsed = await runCourierJson(label, joined, opts)
  return parsed
}

module.exports = {
  CourierTransportError,
  badCourierAnswer,
  extractJson,
  helperResult,
  markerSliceStdout,
  runCourierJson,
  runCourierMarkedJson,
  runCourierMarkedText,
  runCourierText,
  runCourierBatchJson,
  setCourierAgent,
}

};

// ===== pr_comment_scrub.js =====
__modules["pr_comment_scrub"] = function (module, exports, require) {
// Pure-JS port of pr_comment.scrub — bundle-safe (no child_process).
const SECRET_KEY_NAMES = 'session[_-]?id|session|sid|token|api[_-]?key|access[_-]?token|refresh[_-]?token|password|passwd|pwd|client[_-]?secret'

const SCRUB_PATTERNS = [
  [new RegExp('^(\\s*(?:authorization|proxy-authorization|cookie|set-cookie|x-api-key|x-api[_-]?key)\\s*:\\s*).+$', 'gim'), '$1[REDACTED]'],
  [new RegExp('(?<!\\w)(x[_-]?api[_-]?key)(?:\\\\?["\'])?\\s*:\\s*(?:\\\\?"[^"\\n]*\\\\?"|\\\\?\'[^\'.\\n]*\\\\?\'|[^\\s}\'",]+)', 'gi'), '$1: [REDACTED]'],
  [/\bbearer\s+[A-Za-z0-9._~+/=-]{8,}/gi, 'Bearer [REDACTED]'],
  [new RegExp('\\b(' + SECRET_KEY_NAMES + '|x[_-]?api[_-]?key)=([^&\\s;"\']+)', 'gi'), '$1=[REDACTED]'],
  [new RegExp('(\\\\?["\'](' + SECRET_KEY_NAMES + ')\\\\?["\']\\s*:\\s*)(?:\\\\?"[^"\\n]*\\\\?"|\\\\?\'[^\'.\\n]*\\\\?\')', 'gi'), '$1[REDACTED]'],
  [/\b([a-z][a-z0-9+.\-]*:\/\/[^/\s:@]+):([^@\s/]+)@/gi, '$1:[REDACTED]@'],
]

function scrub(text) {
  let out = String(text || '')
  for (const [pattern, repl] of SCRUB_PATTERNS) {
    out = out.replace(pattern, repl)
  }
  return out
}

module.exports = { scrub }

};

// ===== test_pilot_deciders.js =====
__modules["test_pilot_deciders"] = function (module, exports, require) {
// plugins/superheroes/lib/test_pilot_deciders.js
// Pure test-pilot decision helpers — no IO, no agent, no Python.
const { normalizeTitle } = require('./circuit_breaker.js')
const prCommentScrub = require('./pr_comment_scrub.js')

const WEB_KEYS = new Set([
  'user_facing', 'userFacing', 'browser', 'route', 'routes', 'page', 'pages', 'frontend',
  'baseUrl', 'base_url', 'dev-server', 'dev_server', 'devServer', 'runnable_web', 'runnableWeb', 'web',
])
const PROFILE_WEB_KEYS = new Set([...WEB_KEYS].filter((k) => k !== 'baseUrl' && k !== 'base_url'))
const NO_BROWSER_KEYS = {
  docs_only: 'docs-only',
  docsOnly: 'docs-only',
  cli_only: 'CLI-only',
  cliOnly: 'CLI-only',
  library_only: 'library-only',
  libraryOnly: 'library-only',
  internal_only: 'internal-only',
  internalOnly: 'internal-only',
}
const DOC_EXTS = new Set(['.md', '.mdx', '.rst', '.txt', '.adoc'])
const CLI_PATH_PARTS = ['/cli/', '/commands/', '/bin/']
const LIB_PATH_PARTS = ['/lib/', '/src/lib/', '/pkg/']
const INTERNAL_PATH_PARTS = ['/internal/', '/private/']
const WEB_EXTS = new Set(['.html', '.css', '.jsx', '.tsx', '.vue', '.svelte'])
const WEB_PATH_PARTS = ['/web/', '/frontend/', '/pages/', '/routes/', '/app/', '/public/']
const BROWSER_SOURCES = new Set(['browser', 'playwright', 'chrome-devtools', 'devtools'])
const DEFAULT_LIMITS = {
  planRecords: 20,
  browserSteps: 80,
  browserPasses: 4,
  browserFixBatches: 3,
  uniqueScenarios: 40,
  seedOperations: 120,
  elapsedSeconds: 3600,
  renderedBytes: 200000,
}
const MAX_BROWSER_FIX_BATCHES = 3
const PATHISH = /(?:\/private)?\/tmp\/\S+|\/[\w./-]+(?::\d+)?/g
const LINE = /:\d+\b/g

function verdict(v, reason) {
  return { verdict: v, reason }
}

function isObject(value) {
  return value === undefined || value === null || (typeof value === 'object' && !Array.isArray(value))
}

function* walk(value) {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    for (const [key, nested] of Object.entries(value)) {
      yield [key, nested]
      yield* walk(nested)
    }
  } else if (Array.isArray(value)) {
    for (const nested of value) yield [null, nested]
  }
}

function truthySignal(obj, keys) {
  if (!obj || typeof obj !== 'object') return null
  for (const [key, value] of walk(obj)) {
    if (keys.has(key) && value !== false && value !== null && value !== '' && !(Array.isArray(value) && value.length === 0) && !(value && typeof value === 'object' && !Array.isArray(value) && Object.keys(value).length === 0)) {
      return key
    }
  }
  return null
}

function files(diff) {
  if (!diff || typeof diff !== 'object') return []
  const list = diff.files || diff.paths || diff.changed_files
  return Array.isArray(list) && list.every((p) => typeof p === 'string') ? list : []
}

function ext(path) {
  const base = path.split('/').pop()
  if (!base.includes('.')) return ''
  return `.${base.split('.').pop().toLowerCase()}`
}

function docsOnly(list) {
  return list.length > 0 && list.every((path) => path.startsWith('docs/') || path.startsWith('documentation/') || DOC_EXTS.has(ext(path)))
}

function pathSignal(list, parts, exts) {
  const extensions = exts || new Set()
  return list.some((path) => {
    const normalized = `/${path.replace(/^\/+|\/+$/g, '')}`
    return parts.some((part) => normalized.includes(part)) || extensions.has(ext(path))
  })
}

function webPathSignal(list) {
  return list.some((path) => {
    const normalized = `/${path.replace(/^\/+|\/+$/g, '')}`
    if (WEB_PATH_PARTS.some((part) => normalized.includes(part))) return true
    return WEB_EXTS.has(ext(path)) && !pathSignal([path], [...CLI_PATH_PARTS, ...LIB_PATH_PARTS, ...INTERNAL_PATH_PARTS])
  })
}

function planFailed(planResult) {
  if (planResult == null) return null
  if (typeof planResult !== 'object') return 'malformed plan result'
  if (planResult.ok === false || planResult.status === 'failed' || planResult.status === 'error') {
    return String(planResult.reason || 'plan derivation failed')
  }
  return null
}

function planEmptyApplicable(planResult) {
  if (!planResult || typeof planResult !== 'object') return false
  const applicable = planResult.applicable === true || planResult.verdict === 'applicable'
  const steps = planResult.steps
  return applicable && Array.isArray(steps) && steps.length === 0
}

function missingRequiredSetup(detectors, profile) {
  let required = []
  if (detectors && typeof detectors === 'object') {
    required = detectors.requires_setup || detectors.required_setup || []
  }
  if (typeof required === 'string') required = [required]
  if (!Array.isArray(required)) return []
  profile = profile && typeof profile === 'object' ? profile : {}
  const missing = []
  for (const key of required) {
    if (typeof key !== 'string') continue
    const val = profile[key]
    if (val == null || val === '' || (Array.isArray(val) && val.length === 0) || (val && typeof val === 'object' && !Array.isArray(val) && Object.keys(val).length === 0)) {
      missing.push(key)
    }
  }
  return missing
}

function coerceJsonObject(value) {
  if (typeof value !== 'string') return value
  try {
    const parsed = JSON.parse(value)
    if (parsed === null || (parsed && typeof parsed === 'object' && !Array.isArray(parsed))) return parsed
  } catch (_e) { /* keep string */ }
  return value
}

function applicabilityDecision(diff, detectors, profile, planResult) {
  if (planResult === undefined) planResult = null
  diff = coerceJsonObject(diff)
  detectors = coerceJsonObject(detectors)
  profile = coerceJsonObject(profile)
  planResult = coerceJsonObject(planResult)
  if (![diff, detectors, profile, planResult].every(isObject)) {
    return verdict('park', 'malformed inputs')
  }
  diff = diff || {}
  detectors = detectors || {}
  profile = profile || {}
  const failed = planFailed(planResult)
  if (failed) return verdict('park', failed)
  if (planEmptyApplicable(planResult)) return verdict('park', 'empty applicable plan derivation')

  const changed = files(diff)
  let webSignal = truthySignal(detectors, WEB_KEYS) || truthySignal(profile, PROFILE_WEB_KEYS) || truthySignal(planResult, WEB_KEYS)
  if (!webSignal && webPathSignal(changed)) webSignal = 'frontend path'

  if (webSignal) {
    const missing = missingRequiredSetup(detectors, profile)
    if (missing.length) return verdict('park', `missing required setup: ${missing.join(', ')}`)
    return verdict('applicable', `browser/user-facing signal: ${webSignal}`)
  }

  for (const [key, label] of Object.entries(NO_BROWSER_KEYS)) {
    if (detectors[key] === true) return verdict('not_applicable', `${label} change with no browser signal`)
  }
  if (docsOnly(changed)) return verdict('not_applicable', 'docs-only change with no browser signal')
  if (pathSignal(changed, CLI_PATH_PARTS)) return verdict('not_applicable', 'CLI-only change with no browser signal')
  if (pathSignal(changed, LIB_PATH_PARTS)) return verdict('not_applicable', 'library-only change with no browser signal')
  if (pathSignal(changed, INTERNAL_PATH_PARTS)) return verdict('not_applicable', 'internal-only change with no browser signal')
  return verdict('park', 'uncertain applicability')
}

function parkAggregation(reason) {
  return { action: 'park', reason }
}

function browserSource(raw) {
  return raw.source || raw.evidenceSource || raw.evidence_source
}

function isBrowserSource(value) {
  if (typeof value !== 'string') return false
  const lower = value.toLowerCase()
  return BROWSER_SOURCES.has(lower) || lower.startsWith('browser:')
}

function limit(byteLimits, key, fallback) {
  if (!byteLimits || typeof byteLimits !== 'object') return fallback
  const aliases = {
    diagnostics: ['diagnostics', 'diagnosticBytes', 'diagnosticsBytes'],
    renderedBytes: ['renderedBytes', 'rendered', 'total'],
  }
  let value
  for (const candidate of aliases[key] || [key]) {
    if (Object.prototype.hasOwnProperty.call(byteLimits, candidate)) {
      value = byteLimits[candidate]
      break
    }
  }
  return typeof value === 'number' && value >= 0 ? value : fallback
}

function byteLength(text) {
  if (typeof Buffer !== 'undefined') return Buffer.byteLength(text, 'utf8')
  return new TextEncoder().encode(text).length
}

function scrubText(text, scrubber, maxBytes) {
  try {
    const out = scrubber(String(text || ''))
    if (byteLength(out) > maxBytes) return [null, 'diagnostics exceed byte limit']
    return [out, null]
  } catch (err) {
    return [null, `scrub failed: ${err && err.message ? err.message : err}`]
  }
}

function aggregateResults(rawResults, opts) {
  opts = opts || {}
  const scrubber = typeof opts.scrubber === 'function' ? opts.scrubber : prCommentScrub.scrub
  const byteLimits = opts.byteLimits || {}
  if (!rawResults || typeof rawResults !== 'object') return parkAggregation('browser results must be a JSON object')
  if (!isBrowserSource(browserSource(rawResults))) return parkAggregation('browser-derived evidence/source is required')

  const diagnosticLimit = limit(byteLimits, 'diagnostics', 20000)
  const records = []
  const steps = rawResults.steps || rawResults.records || []
  for (const step of steps) {
    if (!step || typeof step !== 'object') continue
    const [notes, noteProblem] = scrubText(step.notes || step.diagnostics || '', scrubber, diagnosticLimit)
    if (noteProblem) return parkAggregation(noteProblem)
    const stepId = step.id || step.stepId || step.step_id
    if (!stepId) return parkAggregation('browser result record is missing a step id')
    const record = {
      stepId: String(stepId),
      status: step.status || step.result || 'unknown',
      notes,
      browserExecuted: true,
    }
    const failureType = step.failureType || step.failure_type || step.kind
    if (failureType != null) record.failureType = String(failureType)
    for (const field of ['summary', 'message']) {
      if (step[field]) {
        const [text, problem] = scrubText(step[field], scrubber, diagnosticLimit)
        if (problem) return parkAggregation(problem)
        record[field] = text
      }
    }
    records.push(record)
  }

  const result = {
    action: 'aggregated',
    source: browserSource(rawResults),
    records,
    coverageRationale: rawResults.coverageRationale || rawResults.coverage_rationale,
  }
  const fixes = []
  for (const fix of rawResults.fixes || []) {
    if (fix && typeof fix === 'object') {
      fixes.push({ sha: fix.sha || fix.commit, summary: scrubber(String(fix.summary || '')) })
    }
  }
  if (fixes.length) result.fixes = fixes
  const renderedLimit = limit(byteLimits, 'renderedBytes', 200000)
  if (byteLength(JSON.stringify(result)) > renderedLimit) {
    return parkAggregation('rendered output exceeds byte limit')
  }
  return result
}

function withinBudget() {
  return { action: 'within_budget' }
}

function parkBudget(reason) {
  return { action: 'park_budget_exceeded', reason }
}

function validNumber(value) {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0
}

function validateMapping(obj, label) {
  if (!obj || typeof obj !== 'object') return `${label} must be a JSON object`
  for (const [key, value] of Object.entries(obj)) {
    if (!validNumber(value)) return `malformed numeric value for ${label}.${key}`
  }
  return null
}

function budgetDecision(counts, limits) {
  const problem = validateMapping(counts, 'counts')
  if (problem) return parkBudget(problem)
  const merged = Object.assign({}, DEFAULT_LIMITS)
  if (limits != null) {
    const limitsProblem = validateMapping(limits, 'limits')
    if (limitsProblem) return parkBudget(limitsProblem)
    Object.assign(merged, limits)
  }
  for (const [key, max] of Object.entries(merged)) {
    const value = Object.prototype.hasOwnProperty.call(counts, key) ? counts[key] : 0
    if (value > max) return parkBudget(`${key} exceeded budget: ${value} > ${max}`)
  }
  return withinBudget()
}

function fixBatch(entry) {
  return entry && typeof entry === 'object' && (entry.type === 'browser_fix_batch' || entry.type === 'fix_batch')
}

function fixBatches(history) {
  return Array.isArray(history) ? history.filter(fixBatch) : []
}

function passSteps(passResult) {
  if (!passResult || typeof passResult !== 'object') return []
  if (Array.isArray(passResult.steps)) return passResult.steps
  if (Array.isArray(passResult.records)) return passResult.records
  return []
}

function stepId(step) {
  if (!step || typeof step !== 'object') return null
  const value = step.id || step.stepId || step.step_id
  return value != null && value !== '' ? String(value) : null
}

function failedSteps(passResult) {
  const failed = []
  for (const step of passSteps(passResult)) {
    if (!step || typeof step !== 'object') continue
    const status = step.status || step.result
    if ((status === 'failed' || status === 'fail') && stepId(step)) failed.push(step)
  }
  return failed
}

function appBug(step) {
  const kind = step.failureType || step.failure_type || step.kind
  return kind === undefined || kind === null || ['app_bug', 'app-bug', 'application'].includes(kind)
}

function failedStepIds(passResult) {
  return failedSteps(passResult).map(stepId).filter(Boolean)
}

function summaryForFailures(failed) {
  return `Fix browser app failures: ${failed.map(stepId).join(', ')}`
}

function scrubSummary(summary) {
  return normalizeTitle(String(summary || '').replace(PATHISH, ' ').replace(LINE, ' '))
}

function statusMap(value) {
  return value && typeof value === 'object' ? value : {}
}

function madeProgress(batch) {
  const before = statusMap(batch.before)
  const after = statusMap(batch.after)
  return Object.entries(before).some(([id, beforeStatus]) => (beforeStatus === 'failed' || beforeStatus === 'fail') && (after[id] === 'passed' || after[id] === 'pass'))
}

function lastTwoSameWithoutProgress(batches) {
  if (batches.length < 2) return null
  const prev = batches[batches.length - 2]
  const latest = batches[batches.length - 1]
  const prevSummary = scrubSummary(prev.summary)
  const latestSummary = scrubSummary(latest.summary)
  if (prevSummary && prevSummary === latestSummary && !madeProgress(prev) && !madeProgress(latest)) {
    return latestSummary
  }
  return null
}

function affectedStepIds(changedFiles, dependencyMap) {
  if (!dependencyMap || typeof dependencyMap !== 'object') return null
  const affected = new Set()
  for (const path of changedFiles || []) {
    const mapped = dependencyMap[path]
    if (!Array.isArray(mapped)) return null
    for (const id of mapped) {
      if (id != null && id !== '') affected.add(String(id))
    }
  }
  return [...affected].sort()
}

function rerunDecision(passResult, changedFiles, dependencyMap) {
  const failedIds = failedStepIds(passResult)
  const affectedIds = affectedStepIds(changedFiles, dependencyMap)
  if (affectedIds == null) return { action: 'rerun_all', failedStepIds: failedIds }
  return {
    action: 'rerun_subset',
    stepIds: [...new Set([...failedIds, ...affectedIds])].sort(),
    failedStepIds: failedIds,
    affectedStepIds: affectedIds,
  }
}

function retryDecisionFromFacts(passResult, history, changedFiles, dependencyMap) {
  const batches = fixBatches(history)
  const failed = failedSteps(passResult)

  if (changedFiles != null && batches.length) {
    return rerunDecision(passResult, changedFiles, dependencyMap)
  }

  if (failed.length && batches.length >= MAX_BROWSER_FIX_BATCHES) {
    return {
      action: 'park_cap_reached',
      reason: 'reached 3 browser fix batches with failed browser steps remaining',
    }
  }

  const noProgress = lastTwoSameWithoutProgress(batches)
  if (failed.length && noProgress) {
    return {
      action: 'park_no_progress',
      reason: `two consecutive browser fix batches made no progress: ${noProgress}`,
    }
  }

  const appFailures = failed.filter(appBug)
  if (appFailures.length) {
    return {
      action: 'fix_batch',
      failedStepIds: appFailures.map(stepId),
      summary: summaryForFailures(appFailures),
    }
  }

  if (failed.length) {
    return {
      action: 'park_unclassified_failure',
      reason: 'one or more browser failures are not app-bug failures',
    }
  }

  return { action: 'passed' }
}

module.exports = {
  applicabilityDecision,
  aggregateResults,
  budgetDecision,
  retryDecisionFromFacts,
}

};

// ===== test_pilot_phase.js =====
__modules["test_pilot_phase"] = function (module, exports, require) {
// plugins/superheroes/lib/test_pilot_phase.js
// Native showrunner test-pilot phase. This module stays dependency-injected so the
// showrunner spine can be smoke-tested without launching browsers or mutating refs.

// Native showrunner test-pilot phase. The orchestrator threads state through five sequential
// helpers, each of which returns `{ done: <terminalResult> }` to short-circuit (park or proceed) or
// the state it produced. Judgment stays in the injected leaves + pure helpers (§10.1); these helpers
// are control flow only.
const deciders = require('./test_pilot_deciders.js')
const prCommentScrub = require('./pr_comment_scrub.js')

async function testPilotPhase(workItem, generation, deps) {
  deps = deps || {}

  const setup = await resolveApplicabilityAndSetup(deps, workItem, generation)
  if (setup.done) return setup.done
  const { context } = setup

  const planned = await preparePlanAndRecords(deps, workItem, context)
  if (planned.done) return planned.done
  const { plan, records, previousStatus } = planned

  const execCtx = await prepareExecutionContext(deps, workItem, context, plan, records, previousStatus)
  if (execCtx.done) return execCtx.done
  const { artifactResult, serverContext, seedResult } = execCtx

  const browser = await runBrowserPasses(deps, workItem, context, plan, records, artifactResult, serverContext, seedResult)
  if (browser.done) return browser.done
  const { combinedAggregated, retryState } = browser

  return finalizeReadiness(deps, workItem, context, plan, records, retryState, combinedAggregated, artifactResult)
}

// Phase 1: resolve context, decide applicability (short-circuit not_applicable / park uncertain),
// validate setup. Returns `{ context }` to proceed or `{ done }` for a terminal.
async function resolveApplicabilityAndSetup(deps, workItem, generation) {
  let context
  try {
    context = await callLeaf(deps.resolveContext, workItem, generation)
  } catch (err) {
    return { done: low(`test-pilot setup failed: ${message(err)}`) }
  }
  if (!context || !context.head) {
    return { done: low('test-pilot setup failed: missing current head') }
  }

  let applicability
  try {
    applicability = deciders.applicabilityDecision(context.diff, context.detectors, context.profile, context.planResult)
  } catch (err) {
    return { done: low(`test-pilot applicability failed: ${message(err)}`) }
  }
  if (!applicability || typeof applicability !== 'object') {
    return { done: low('test-pilot applicability failed: no verdict') }
  }

  if (applicability.verdict === 'not_applicable') {
    const status = {
      schemaVersion: 1,
      verdict: 'not_applicable',
      workItem,
      branch: context.branch,
      head: context.head,
      rationale: applicability.rationale || applicability.reason || 'no browser-verifiable workflow changed',
    }
    const wrote = await writeStatus(deps, workItem, status)
    if (!wrote.ok) return { done: low(wrote.reason) }
    return { done: { confidence: 'high', assumptions: [] } }
  }

  if (applicability.verdict !== 'applicable') {
    return { done: low(applicability.reason || 'test-pilot applicability is uncertain') }
  }

  const setupProblem = validateSetup(context)
  if (setupProblem) {
    return { done: await parkLow(deps, workItem, context, setupProblem) }
  }

  return { context }
}

// Phase 2: derive the plan, prepare + validate plan records, write the plan milestones. Returns
// `{ plan, records, previousStatus }` to proceed or `{ done }` for a terminal.
async function preparePlanAndRecords(deps, workItem, context) {
  const previousStatus = await readPreviousStatus(deps, workItem)

  let plan
  try {
    plan = await callLeaf(deps.planTests || deps.derivePlan, context)
  } catch (err) {
    return { done: low(`test-pilot plan derivation failed: ${message(err)}`) }
  }
  if (plan && plan.confidence === 'low') {
    return { done: low(plan.reason || 'test-pilot plan derivation is low-confidence') }
  }
  plan = normalizePlan(plan)
  if (!plan.records.length) {
    return { done: await parkLow(deps, workItem, context, 'applicable test-pilot plan is empty') }
  }
  const generatedStoreProblem = generatedInRepoStoreProblem(plan.records)
  if (generatedStoreProblem) {
    return { done: await parkLow(deps, workItem, context, generatedStoreProblem) }
  }
  const mergedRecords = mergePriorStepState(plan.records, previousStatus)
  const skippedProblem = validateSkippedPreservation(mergedRecords)
  if (skippedProblem) {
    return { done: low(skippedProblem) }
  }
  const dedupeProblem = validateUniqueIds(mergedRecords)
  if (dedupeProblem) {
    return { done: low(dedupeProblem) }
  }
  plan.records = mergedRecords
  let wrote = await writeStatus(deps, workItem, milestoneStatus(context, workItem, 'plan-derived', {
    planRecords: plan.records,
  }))
  if (!wrote.ok) return { done: low(wrote.reason) }

  let prepared
  try {
    prepared = await callLeaf(deps.preparePlanRecords, plan, context, previousStatus)
  } catch (err) {
    return { done: low(`test-pilot plan record preparation failed: ${message(err)}`) }
  }
  const recordProblem = planRecordProblem(prepared)
  if (recordProblem) {
    return { done: await parkLow(deps, workItem, context, recordProblem) }
  }
  const records = mergePriorStepState(prepared.records, previousStatus)
  const preparedSkippedProblem = validateSkippedPreservation(records)
  if (preparedSkippedProblem) {
    return { done: low(preparedSkippedProblem) }
  }
  const preparedDedupeProblem = validateUniqueIds(records)
  if (preparedDedupeProblem) {
    return { done: low(preparedDedupeProblem) }
  }
  wrote = await writeStatus(deps, workItem, milestoneStatus(context, workItem, 'plan-records-ready', {
    planRecords: records,
  }))
  if (!wrote.ok) return { done: low(wrote.reason) }

  return { plan, records, previousStatus }
}

// Phase 3: prepare artifacts, resolve the server, seed records — each with its readiness milestone.
// Returns `{ artifactResult, serverContext, seedResult }` to proceed or `{ done }` for a terminal.
async function prepareExecutionContext(deps, workItem, context, plan, records, previousStatus) {
  if (typeof deps.prepareTestRun === 'function') {
    let folded
    try {
      folded = await callLeaf(deps.prepareTestRun, { plan, records, context, previousStatus, workItem })
    } catch (err) {
      return { done: low(`test-pilot preparation failed: ${message(err)}`) }
    }
    const artifactResult = folded && folded.artifactResult
    const serverContext = folded && folded.serverContext
    const seedResult = folded && folded.seedResult
    const artifactProblem = artifactReadinessProblem(artifactResult)
    if (artifactProblem) return { done: low(artifactProblem) }
    const serverProblem = serverContextProblem(serverContext, context)
    if (serverProblem) return { done: low(serverProblem) }
    const seedProblem = seedReadinessProblem(seedResult)
    if (seedProblem) return { done: low(seedProblem) }
    const wrote = await writeStatus(deps, workItem, milestoneStatus(context, workItem, 'seed-ready', {
      planRecords: records,
      artifacts: artifactResult.artifacts,
      server: publicServerContext(serverContext),
      seed: seedResult.status || seedResult,
    }))
    if (!wrote.ok) return { done: low(wrote.reason) }
    return { artifactResult, serverContext, seedResult }
  }

  let artifactResult
  try {
    artifactResult = await callLeaf(deps.prepareArtifacts, {
      plan: Object.assign({}, plan, { records }),
      records,
      context,
      previousStatus,
    })
  } catch (err) {
    return { done: low(`test-pilot artifact preparation failed: ${message(err)}`) }
  }
  const artifactProblem = artifactReadinessProblem(artifactResult)
  if (artifactProblem) {
    return { done: low(artifactProblem) }
  }
  let wrote = await writeStatus(deps, workItem, milestoneStatus(context, workItem, 'artifacts-ready', {
    planRecords: records,
    artifacts: artifactResult.artifacts,
    prPosting: artifactResult.posting || artifactResult.prPosting,
    fallback: artifactResult.fallback,
  }))
  if (!wrote.ok) return { done: low(wrote.reason) }

  let serverContext
  try {
    serverContext = await callLeaf(deps.resolveServer, context, records)
  } catch (err) {
    return { done: low(`test-pilot server resolution failed: ${message(err)}`) }
  }
  const serverProblem = serverContextProblem(serverContext, context)
  if (serverProblem) {
    return { done: low(serverProblem) }
  }
  wrote = await writeStatus(deps, workItem, milestoneStatus(context, workItem, 'server-ready', {
    planRecords: records,
    artifacts: artifactResult.artifacts,
    server: publicServerContext(serverContext),
  }))
  if (!wrote.ok) return { done: low(wrote.reason) }

  let seedResult
  try {
    seedResult = await callLeaf(deps.seedRecords, records, context)
  } catch (err) {
    return { done: low(`test-pilot seed preparation failed: ${message(err)}`) }
  }
  const seedProblem = seedReadinessProblem(seedResult)
  if (seedProblem) {
    return { done: low(seedProblem) }
  }
  wrote = await writeStatus(deps, workItem, milestoneStatus(context, workItem, 'seed-ready', {
    planRecords: records,
    artifacts: artifactResult.artifacts,
    server: publicServerContext(serverContext),
    seed: seedResult.status || seedResult,
  }))
  if (!wrote.ok) return { done: low(wrote.reason) }

  return { artifactResult, serverContext, seedResult }
}

// Phase 4: run browser passes, dispatch app-bug fix batches + review-code stabilization, until the
// evidence is clean (returns { combinedAggregated, retryState }) or a park condition returns { done }.
async function runBrowserPasses(deps, workItem, context, plan, records, artifactResult, serverContext, seedResult) {
  const retryState = {
    fixBatchHistory: [],
    currentHead: context.head,
    browserEvidenceHead: context.head,
    browserPasses: [],
    allRecords: records,
  }
  let aggregated
  let combinedAggregated = null
  let rerunScope = null
  let browserRecords = records
  let stabilizationCycle = 0
  while (true) {
    const budget = await budgetCheck(deps, 'browser-pass', {
      workItem,
      head: retryState.currentHead,
      rerunScope,
      fixBatchHistory: retryState.fixBatchHistory,
      counts: {
        browserPasses: retryState.browserPasses.length + 1,
        browserFixBatches: retryState.fixBatchHistory.length,
      },
    })
    if (!budget.ok) return { done: low(budget.reason) }

    let rawResults
    try {
      rawResults = await runWithServer(deps, serverContext, async (activeServer) => {
        const browserContext = browserLeafContext(
          context,
          activeServer,
          browserRecords,
          artifactResult,
          seedResult,
          rerunScope,
          retryState,
        )
        return callLeaf(deps.browserPass || deps.runBrowserPass, browserContext)
      })
    } catch (err) {
      return { done: low(`test-pilot browser execution failed: ${message(err)}`) }
    }
    const originProblem = browserOriginProblem(rawResults, serverContext)
    if (originProblem) {
      return { done: low(originProblem) }
    }

    try {
      aggregated = deciders.aggregateResults(rawResults, { scrubber: prCommentScrub.scrub })
    } catch (err) {
      return { done: low(`test-pilot result aggregation failed: ${message(err)}`) }
    }
    const aggregationProblem = resultAggregationProblem(aggregated)
    if (aggregationProblem) {
      return { done: low(aggregationProblem) }
    }

    retryState.browserEvidenceHead = retryState.currentHead
    retryState.browserPasses.push({
      head: retryState.browserEvidenceHead,
      rerunScope: rerunScope || { action: 'initial' },
      records: statusMap(aggregated),
    })
    completeLatestBatchAfter(retryState.fixBatchHistory, aggregated)
    combinedAggregated = mergeAggregatedEvidence(combinedAggregated, aggregated)

    const evidenceProblem = resultEvidenceProblem(combinedAggregated, records)
    if (!evidenceProblem) {
      const stabilization = await stabilizeReviewCode(deps, workItem, context, retryState, combinedAggregated, records)
      if (!stabilization.ok) {
        const wrote = await writeRetryStatus(deps, workItem, context, retryState, combinedAggregated, records, stabilization.reason)
        if (!wrote.ok) return { done: low(wrote.reason) }
        return { done: low(stabilization.reason) }
      }
      if (stabilization.changed) {
        stabilizationCycle += 1
        if (stabilizationCycle > 2) {
          const reason = 'review-code stabilization cycle cap reached'
          const wrote = await writeRetryStatus(deps, workItem, context, retryState, combinedAggregated, records, reason)
          if (!wrote.ok) return { done: low(wrote.reason) }
          return { done: low(reason) }
        }
        retryState.currentHead = stabilization.head || retryState.currentHead
        retryState.reviewStabilizationCycle = stabilizationCycle
        retryState.reviewCoverageHead = stabilization.reviewCoverageHead || stabilization.head
        rerunScope = { action: 'rerun_all', reason: 'review-code changed branch' }
        browserRecords = records
        combinedAggregated = null
        continue
      }
      retryState.reviewStabilizationCycle = stabilizationCycle
      retryState.reviewCoverageHead = stabilization.reviewCoverageHead || retryState.currentHead
      retryState.verifyPassedHead = stabilization.verifyPassedHead || retryState.currentHead
      return { combinedAggregated, retryState }
    }

    const failed = failedBrowserRecords(aggregated)
    if (!failed.length) {
      const retryWrite = await writeRetryStatus(deps, workItem, context, retryState, aggregated, records, evidenceProblem)
      if (!retryWrite.ok) return { done: low(retryWrite.reason) }
      return { done: low(evidenceProblem) }
    }

    const decision = await retryDecision(deps, aggregated, retryState.fixBatchHistory)
    if (decision.action !== 'fix_batch') {
      const reason = decision.reason || evidenceProblem
      const retryWrite = await writeRetryStatus(deps, workItem, context, retryState, aggregated, records, reason)
      if (!retryWrite.ok) return { done: low(retryWrite.reason) }
      return { done: low(reason) }
    }

    const failures = collectAppBugFailures(aggregated)
    if (!failures.length || failures.length !== failed.length) {
      const reason = 'one or more browser failures are not app-bug failures'
      const retryWrite = await writeRetryStatus(deps, workItem, context, retryState, aggregated, records, reason)
      if (!retryWrite.ok) return { done: low(retryWrite.reason) }
      return { done: low(reason) }
    }

    const fixBudget = await budgetCheck(deps, 'fix-batch', {
      workItem,
      failures,
      head: retryState.currentHead,
      fixBatchHistory: retryState.fixBatchHistory,
    })
    if (!fixBudget.ok) return { done: low(fixBudget.reason) }

    const summary = decision.summary || failureSummary(failures)
    const batch = {
      type: 'browser_fix_batch',
      batchNumber: retryState.fixBatchHistory.length + 1,
      intent: true,
      headBefore: retryState.browserEvidenceHead,
      failedStepIds: failures.map((failure) => failure.stepId),
      summary,
      scrubbedSummary: scrubFailureSummary(summary),
      before: statusMap(aggregated),
    }
    retryState.fixBatchHistory.push(batch)

    let fixResult
    try {
      fixResult = await dispatchFixBatch(failures, deps, {
        workItem,
        context,
        records,
        passResult: aggregated,
        fixBatchHistory: retryState.fixBatchHistory,
        batch,
      })
    } catch (err) {
      return { done: low(`test-pilot browser fix batch failed: ${message(err)}`) }
    }
    if (!fixResult || fixResult.ok === false || fixResult.action === 'park' || fixResult.confidence === 'low') {
      return { done: low((fixResult && (fixResult.reason || fixResult.message)) || 'test-pilot browser fix batch parked') }
    }

    const clean = await ensureCleanWorktreeAfterFix(fixResult, deps, { workItem, context, batch })
    if (!clean.ok) return { done: low(clean.reason) }

    const reconciled = await reconcileCommittedMutations(fixResult, retryState.fixBatchHistory, batch, deps, {
      workItem,
      context,
    })
    if (!reconciled.ok) return { done: low(reconciled.reason) }

    batch.intent = false
    batch.commitShas = normalizeShas(reconciled.commitShas || fixResult.commitShas || fixResult.commits || fixResult.shas)
    batch.changedFiles = normalizeStrings(reconciled.changedFiles || fixResult.changedFiles || fixResult.files)
    batch.headAfter = reconciled.head || fixResult.head || batch.commitShas[batch.commitShas.length - 1] || retryState.currentHead
    retryState.currentHead = batch.headAfter

    const dependencyMap = deps.dependencyMap || aggregated.dependencyMap || plan.dependencyMap || context.dependencyMap
    const rerunDecision = await retryDecision(
      deps,
      aggregated,
      retryState.fixBatchHistory,
      batch.changedFiles,
      dependencyMap,
    )
    rerunScope = normalizeRerunScope(rerunDecision)
    batch.rerunScope = rerunScope
    browserRecords = recordsForRerun(records, rerunScope)

    const wrote = await writeStatus(deps, workItem, milestoneStatus(context, workItem, 'fix-batch-ready', {
      planRecords: records,
      artifacts: artifactResult.artifacts,
      server: publicServerContext(serverContext),
      seed: seedResult.status || seedResult,
      fixBatchHistory: retryState.fixBatchHistory,
      browserEvidenceHead: retryState.browserEvidenceHead,
      currentHead: retryState.currentHead,
      lastBrowserResult: aggregated,
    }))
    if (!wrote.ok) return { done: low(wrote.reason) }
  }
}

// Phase 5: restore the seed baseline, publish the final artifacts + tested head, write the applicable
// status. Returns the high-confidence terminal, or low() on any park.
async function finalizeReadiness(deps, workItem, context, plan, records, retryState, combinedAggregated, artifactResult) {
  const baselineResult = await restoreFinalBaseline(deps, records, context, retryState)
  if (!baselineResult.ok) return low(baselineResult.reason)

  const finalArtifacts = await ensureFinalArtifacts(deps, {
    workItem,
    context,
    records,
    aggregated: combinedAggregated,
    artifacts: artifactResult.artifacts,
    baseline: baselineResult.baseline,
    retryState,
  })
  if (!finalArtifacts.ok) return low(finalArtifacts.reason)

  const publishResult = await publishFinalHead(deps, workItem, context, retryState, {
    records,
    artifacts: finalArtifacts.artifacts,
    baseline: baselineResult.baseline,
    aggregated: combinedAggregated,
  })
  if (!publishResult.ok) return low(publishResult.reason)

  const finalStatus = {
    schemaVersion: 1,
    verdict: 'applicable',
    workItem,
    branch: context.branch,
    head: retryState.currentHead,
    browserEvidenceHead: retryState.browserEvidenceHead,
    records: mergeAllowedSkippedResults(combinedAggregated.records, records),
    fixBatchHistory: retryState.fixBatchHistory,
    browserPasses: retryState.browserPasses,
    artifacts: finalArtifacts.artifacts,
    prPosting: finalArtifacts.posting || finalArtifacts.prPosting || artifactResult.posting || artifactResult.prPosting,
    baseline: baselineResult.baseline,
    review: context.review || { head: retryState.reviewCoverageHead || retryState.currentHead },
    verify: context.verify || { result: 'pass', head: retryState.verifyPassedHead || retryState.currentHead },
    remotePr: publishResult.remotePr || publishResult.remotePR || { head: retryState.currentHead },
  }
  if (combinedAggregated.coverageRationale || plan.coverageRationale) {
    finalStatus.coverageRationale = combinedAggregated.coverageRationale || plan.coverageRationale
  }
  if (combinedAggregated.fixes) finalStatus.fixes = combinedAggregated.fixes
  if (combinedAggregated.verify) finalStatus.verify = combinedAggregated.verify
  const wrote = await writeStatus(deps, workItem, finalStatus)
  if (!wrote.ok) return low(wrote.reason)

  return { confidence: 'high', assumptions: [] }
}

function validateSetup(context) {
  if (!context.profile) {
    return 'test-pilot setup missing calibration/profile'
  }
  if (!context.browserTool) {
    return 'test-pilot setup missing browser tool'
  }
  const baseUrl = context.baseUrl || (context.profile && (context.profile.baseUrl || context.profile.base_url))
  if (!baseUrl) {
    return 'test-pilot setup missing baseUrl'
  }
  const allowed = context.allowedOrigins || context.allowed_origins || (context.profile && (context.profile.allowedOrigins || context.profile.allowed_origins))
  if (!Array.isArray(allowed) || allowed.length === 0) {
    return 'test-pilot setup missing allowedOrigins'
  }
  return null
}

async function writeStatus(deps, workItem, status) {
  try {
    if (deps.writeStatus) {
      // status already carries workItem (milestoneStatus / terminal statuses set it); the writer
      // contract is writeStatus(status) — don't pass a 2nd arg no implementation reads.
      const out = await deps.writeStatus(status)
      if (out && out.ok === false) return { ok: false, reason: out.reason || 'test-pilot status write failed' }
      if (out && out.read_back === false) return { ok: false, reason: out.reason || 'test-pilot status read-back mismatch' }
      return { ok: true }
    }
  } catch (err) {
    return { ok: false, reason: `test-pilot status write failed: ${message(err)}` }
  }
  return { ok: false, reason: 'test-pilot status writer unavailable' }
}

async function readPreviousStatus(deps, workItem) {
  if (typeof deps.readStatus !== 'function') return null
  try {
    const out = await deps.readStatus(workItem)
    return out && typeof out === 'object' ? out : null
  } catch (_) {
    return null
  }
}

function normalizePlan(plan) {
  const source = plan && typeof plan === 'object' ? plan : {}
  const records = source.records || source.planRecords
  return Object.assign({}, source, { records: Array.isArray(records) ? records : [] })
}

function generatedInRepoStoreProblem(records) {
  for (const record of records) {
    const store = record && (record.store || record.planStore || record.generatedStore)
    const location = store && (store.location || store.mode)
    const generated = (store && store.generated === true) || record.generated === true || record.generatedManifest === true
    if (generated && (location === 'in_repo' || location === 'in-repo')) {
      return 'generated in-repo plan store writes must park before touching worktree'
    }
  }
  return null
}

function previousRecords(status) {
  return status && Array.isArray(status.records) ? status.records : []
}

function stepKey(value) {
  if (!value || typeof value !== 'object') return null
  const raw = value.id || value.stepId || value.step_id
  return raw == null || raw === '' ? null : String(raw)
}

function mergePriorStepState(records, previousStatus) {
  const prior = new Map()
  for (const record of previousRecords(previousStatus)) {
    const key = stepKey(record)
    if (key) prior.set(key, record)
  }
  return records.map((record) => {
    if (!record || typeof record !== 'object') return record
    const seen = new Set()
    const steps = []
    for (const step of Array.isArray(record.steps) ? record.steps : []) {
      if (!step || typeof step !== 'object') continue
      const key = stepKey(step)
      if (key && seen.has(key)) continue
      if (key) seen.add(key)
      const merged = Object.assign({}, step)
      const old = key ? prior.get(key) : null
      if (old) {
        for (const field of ['checked', 'checkboxState', 'humanChecked', 'humanCheckboxState']) {
          if (old[field] !== undefined && merged[field] === undefined) merged[field] = old[field]
        }
        if (merged.priorResult === undefined) merged.priorResult = old.result || old.status
      }
      if (Array.isArray(merged.scenarioIds)) {
        merged.scenarioIds = [...new Set(merged.scenarioIds.map(String).filter(Boolean))]
      }
      steps.push(merged)
    }
    return Object.assign({}, record, { steps })
  })
}

function validateSkippedPreservation(records) {
  for (const record of records) {
    for (const step of (record && Array.isArray(record.steps) ? record.steps : [])) {
      const skipped = step.status === 'skipped' || step.result === 'skipped' || step.skipped === true
      if (!skipped) continue
      if (!stepKey(step) || !step.removalReason || !step.priorResult || !step.planContext) {
        return 'skipped step preservation missing step id, removal reason, prior result, or updated plan context'
      }
    }
  }
  return null
}

function validateUniqueIds(records) {
  const stepIds = new Set()
  const scenarioIds = new Set()
  for (const record of records) {
    if (!record || typeof record !== 'object') return 'malformed plan records'
    const steps = record.steps
    if (!Array.isArray(steps) || steps.length === 0) return 'malformed plan records: steps missing'
    for (const step of steps) {
      const key = stepKey(step)
      if (!key) return 'malformed plan records: step id missing'
      if (stepIds.has(key)) return `duplicate browser step id: ${key}`
      stepIds.add(key)
      for (const sid of Array.isArray(step.scenarioIds) ? step.scenarioIds : []) {
        const value = String(sid)
        if (scenarioIds.has(value)) continue
        scenarioIds.add(value)
      }
    }
  }
  return null
}

function planRecordProblem(prepared) {
  if (!prepared || typeof prepared !== 'object') return 'test-pilot plan record preparation returned no result'
  if (prepared.confidence === 'low') return prepared.reason || 'test-pilot plan record preparation is low-confidence'
  if (prepared.action === 'park' || prepared.ok === false) return prepared.reason || 'test-pilot plan records are invalid'
  if (!Array.isArray(prepared.records) || prepared.records.length === 0) return 'test-pilot plan records missing after preparation'
  return null
}

function artifactReadinessProblem(result) {
  if (!result || typeof result !== 'object') return 'test-pilot artifact preparation returned no result'
  if (result.confidence === 'low') return result.reason || 'test-pilot artifact preparation is low-confidence'
  if (result.action === 'park' || result.ok === false) return result.reason || 'test-pilot artifact preparation parked'
  if (!result.artifacts || !result.artifacts.plan) return 'plan artifact missing before seed/browser execution'
  return null
}

function seedReadinessProblem(result) {
  if (!result || typeof result !== 'object') return 'test-pilot seed preparation returned no result'
  if (result.confidence === 'low') return result.reason || 'test-pilot seed preparation is low-confidence'
  if (result.action === 'park' || result.ok === false) return result.reason || 'test-pilot seed preparation parked'
  if (!['ready_for_browser', 'verified', 'ready'].includes(result.action) && result.ready !== true) {
    return 'test-pilot seed state was not verified before browser execution'
  }
  return null
}

function serverContextProblem(server, context) {
  if (!server || typeof server !== 'object') return 'test-pilot server resolution returned no context'
  if (server.verdict === 'park' || server.action === 'park' || server.ok === false) return server.reason || 'test-pilot server resolution parked'
  if (!['ready_external', 'managed'].includes(server.verdict)) return 'test-pilot server resolution did not confirm external or managed server'
  if (!server.baseUrl) return 'test-pilot server resolution missing baseUrl'
  const allowed = server.allowedOrigins || server.allowed_origins || context.allowedOrigins || context.allowed_origins || (context.profile && context.profile.allowedOrigins)
  if (!Array.isArray(allowed) || !allowed.length) return 'test-pilot server resolution missing allowedOrigins'
  server.allowedOrigins = allowed
  if (server.verdict === 'managed') {
    if (!Array.isArray(server.command) || !server.command.length) return 'managed server command argv missing'
    if (server.shell !== false) return 'managed server must launch with shell=false'
  }
  return null
}

function publicServerContext(server) {
  const out = Object.assign({}, server)
  if (out.handle) out.handle = '[managed]'
  return out
}

async function runWithServer(deps, serverContext, run) {
  if (serverContext.verdict === 'managed') {
    return callLeaf(deps.withManagedServer, serverContext, run)
  }
  return run(serverContext)
}

function browserLeafContext(context, server, records, artifacts, seed, rerunScope, retryState) {
  return {
    workItem: context.workItem,
    branch: context.branch,
    head: retryState && retryState.currentHead ? retryState.currentHead : context.head,
    profile: context.profile,
    browserTool: context.browserTool,
    baseUrl: server.baseUrl,
    allowedOrigins: server.allowedOrigins,
    server,
    records,
    allRecords: retryState ? retryState.allRecords : undefined,
    artifacts,
    seed,
    rerunScope,
    fixBatchHistory: retryState ? retryState.fixBatchHistory : undefined,
  }
}

function browserOriginProblem(rawResults, server) {
  const allowed = new Set((server.allowedOrigins || []).map(originOf).filter(Boolean))
  allowed.add(originOf(server.baseUrl))
  const urls = []
  collectUrls(rawResults, urls)
  for (const url of urls) {
    const origin = originOf(url)
    if (origin && !allowed.has(origin)) {
      return `off-origin browser navigation/result cannot count: ${bounded(url)}`
    }
  }
  const resultOrigin = originOf(rawResults && rawResults.baseUrl)
  if (resultOrigin && !allowed.has(resultOrigin)) {
    return `off-origin browser navigation/result cannot count: ${bounded(rawResults.baseUrl)}`
  }
  return null
}

function collectUrls(value, urls) {
  if (!value || typeof value !== 'object') return
  if (Array.isArray(value)) {
    value.forEach((entry) => collectUrls(entry, urls))
    return
  }
  for (const key of ['url', 'currentUrl', 'current_url', 'navigationUrl', 'navigation_url', 'baseUrl']) {
    if (typeof value[key] === 'string') urls.push(value[key])
  }
  for (const key of ['steps', 'records', 'navigations']) {
    collectUrls(value[key], urls)
  }
}

function originOf(url) {
  if (typeof url !== 'string' || !url) return null
  try {
    return new URL(url).origin
  } catch (_) {
    return null
  }
}

function bounded(value) {
  const text = String(value || '')
  return text.length > 200 ? `${text.slice(0, 197)}...` : text
}

function resultAggregationProblem(aggregated) {
  if (!aggregated || typeof aggregated !== 'object') return 'test-pilot result aggregation returned no result'
  if (aggregated.confidence === 'low') return aggregated.reason || 'test-pilot result aggregation is low-confidence'
  if (aggregated.action === 'park' || aggregated.ok === false) return aggregated.reason || 'test-pilot result aggregation parked'
  if (!Array.isArray(aggregated.records) || aggregated.records.length === 0) return 'no browser-executed records were produced'
  return null
}

// Single source of truth for "this record is browser-derived evidence". MUST stay byte-for-byte
// equivalent to test_pilot_status.py `_browser_executed` (the mark-ready gate's check) — if the two
// drift, the in-phase readiness check and the mark-ready gate can disagree on the same status.
// The `browser === true` alias is the one the Python accepts that the JS previously omitted.
function browserExecutedRecord(record) {
  return !!record && typeof record === 'object' && (
    record.browserExecuted === true ||
    record.browser_executed === true ||
    record.browser === true ||
    record.kind === 'browser' ||
    record.type === 'browser'
  )
}

function resultEvidenceProblem(aggregated, records) {
  const aggregationProblem = resultAggregationProblem(aggregated)
  if (aggregationProblem) return aggregationProblem
  const expected = new Set()
  for (const record of records) {
    for (const step of record.steps || []) {
      const key = stepKey(step)
      if (key && !(step.status === 'skipped' || step.result === 'skipped')) expected.add(key)
    }
  }
  const seen = new Set()
  for (const record of aggregated.records) {
    const key = stepKey(record)
    if (!key) return 'browser-derived pass/fail evidence missing step id'
    const status = record.status || record.result
    if (status !== 'passed' && status !== 'pass') return 'skipped, incomplete, or failing browser records park before readiness'
    if (!browserExecutedRecord(record)) {
      return 'every browser step must have browser-derived pass/fail evidence'
    }
    seen.add(key)
  }
  for (const key of expected) {
    if (!seen.has(key)) return `browser-derived pass/fail evidence missing for step ${key}`
  }
  return null
}

function failedBrowserRecords(passResult) {
  const out = []
  for (const record of passRecords(passResult)) {
    const status = resultStatus(record)
    const key = stepKey(record)
    if ((status === 'failed' || status === 'fail') && key) out.push(record)
  }
  return out
}

function collectAppBugFailures(passResult) {
  return failedBrowserRecords(passResult)
    .filter(isAppBugFailure)
    .map((record) => {
      const key = stepKey(record)
      return Object.assign({}, record, {
        stepId: key,
        failureType: record.failureType || record.failure_type || record.kind || 'app_bug',
        summary: record.summary || record.notes || record.message || `browser step failed: ${key}`,
      })
    })
}

function passRecords(passResult) {
  if (!passResult || typeof passResult !== 'object') return []
  if (Array.isArray(passResult.records)) return passResult.records
  if (Array.isArray(passResult.steps)) return passResult.steps
  return []
}

function resultStatus(record) {
  return record && (record.status || record.result)
}

function isAppBugFailure(record) {
  const kind = record && (record.failureType || record.failure_type || record.kind)
  return kind === undefined || kind === null || ['app_bug', 'app-bug', 'application'].includes(kind)
}

function statusMap(passResult) {
  const out = {}
  for (const record of passRecords(passResult)) {
    const key = stepKey(record)
    if (key) out[key] = resultStatus(record)
  }
  return out
}

function mergeAggregatedEvidence(previous, current) {
  if (!previous) return Object.assign({}, current, { records: passRecords(current).map((record) => Object.assign({}, record)) })
  const byId = new Map()
  const order = []
  for (const record of passRecords(previous)) {
    const key = stepKey(record)
    if (!key) continue
    byId.set(key, Object.assign({}, record))
    order.push(key)
  }
  for (const record of passRecords(current)) {
    const key = stepKey(record)
    if (!key) continue
    if (!byId.has(key)) order.push(key)
    byId.set(key, Object.assign({}, record))
  }
  const merged = Object.assign({}, previous, current)
  merged.records = order.map((key) => byId.get(key)).filter(Boolean)
  return merged
}

function completeLatestBatchAfter(history, passResult) {
  const latest = latestFixBatch(history)
  if (latest && latest.after === undefined) latest.after = statusMap(passResult)
}

function latestFixBatch(history) {
  if (!Array.isArray(history)) return null
  for (let i = history.length - 1; i >= 0; i -= 1) {
    const entry = history[i]
    if (entry && (entry.type === 'browser_fix_batch' || entry.type === 'fix_batch')) return entry
  }
  return null
}

async function budgetCheck(deps, phase, payload) {
  const counts = payload && payload.counts ? payload.counts : {
    browserPasses: payload && typeof payload.browserPasses === 'number'
      ? payload.browserPasses
      : (payload && payload.rerunScope ? 1 : 0),
    browserFixBatches: payload && payload.fixBatchHistory ? payload.fixBatchHistory.length : 0,
  }
  try {
    if (typeof deps.budgetCheck === 'function') {
      const out = await deps.budgetCheck(phase, payload)
      if (out === false) return { ok: false, reason: `test-pilot budget exhausted before ${phase}` }
      if (out && out.ok === false) return { ok: false, reason: out.reason || `test-pilot budget exhausted before ${phase}` }
      if (out && out.action === 'park') return { ok: false, reason: out.reason || `test-pilot budget exhausted before ${phase}` }
      return { ok: true }
    }
    const out = deciders.budgetDecision(counts)
    if (out.action !== 'within_budget') {
      return { ok: false, reason: out.reason || `test-pilot budget exhausted before ${phase}` }
    }
    return { ok: true }
  } catch (err) {
    return { ok: false, reason: `test-pilot budget check failed before ${phase}: ${message(err)}` }
  }
}

async function retryDecision(deps, passResult, history, changedFiles, dependencyMap) {
  try {
    if (typeof deps.retryDecide === 'function') {
      return await deps.retryDecide(passResult, history, changedFiles, dependencyMap)
    }
    return deciders.retryDecisionFromFacts(passResult, history, changedFiles, dependencyMap)
  } catch (err) {
    return { action: 'park_retry_decision_failed', reason: `test-pilot retry decision failed: ${message(err)}` }
  }
}

function fixBatches(history) {
  return Array.isArray(history)
    ? history.filter((entry) => entry && (entry.type === 'browser_fix_batch' || entry.type === 'fix_batch'))
    : []
}

function failureSummary(failures) {
  return `Fix browser app failures: ${failures.map((failure) => failure.stepId).join(', ')}`
}

function scrubFailureSummary(summary) {
  return bounded(String(summary || '')
    .replace(/(?:\/private)?\/tmp\/\S+|\/[\w./-]+(?::\d+)?/g, ' ')
    .replace(/:\d+\b/g, ' ')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, ' ')
    .trim()
    .replace(/\s+/g, ' '))
}

async function dispatchFixBatch(failures, deps, details) {
  if (typeof deps.dispatchFixBatch !== 'function') throw new Error('required leaf is unavailable')
  return deps.dispatchFixBatch(failures, details)
}

async function ensureCleanWorktreeAfterFix(fixResult, deps, details) {
  if (typeof deps.ensureCleanWorktreeAfterFix === 'function') {
    try {
      const out = await deps.ensureCleanWorktreeAfterFix(fixResult, details)
      if (out && out.ok === false) return { ok: false, reason: out.reason || 'dirty fix leftovers after lease reset failed' }
      if (out && out.action === 'park') return { ok: false, reason: out.reason || 'dirty fix leftovers after lease reset failed' }
      return { ok: true }
    } catch (err) {
      return { ok: false, reason: `test-pilot clean worktree guard failed: ${message(err)}` }
    }
  }
  if (fixResult && (fixResult.dirty || fixResult.uncommitted || fixResult.untracked)) {
    return { ok: false, reason: 'dirty fix leftovers require an injected lease-fenced reset before retry' }
  }
  return { ok: true }
}

function reconcileCommittedMutations(fixResult, history, intent, deps, details) {
  if (deps && typeof deps.reconcileCommittedMutations === 'function') {
    return deps.reconcileCommittedMutations(fixResult, history, intent, details)
  }
  const commitShas = normalizeShas(fixResult && (fixResult.commitShas || fixResult.commits || fixResult.shas))
  const changedFiles = normalizeStrings(fixResult && (fixResult.changedFiles || fixResult.files))
  const head = fixResult && (fixResult.head || fixResult.headAfter)
  const committed = fixResult && (
    fixResult.cleanCommittedMutations ||
    fixResult.committedMutations ||
    fixResult.committed === true ||
    head ||
    commitShas.length
  )
  const hasHistory = Array.isArray(history) && history.includes(intent)
  if (committed && !commitShas.length && !hasHistory) {
    return {
      ok: false,
      reason: 'clean committed mutations without matching browser fix-batch history cannot be reconciled deterministically',
    }
  }
  return { ok: true, commitShas, changedFiles, head }
}

function normalizeRerunScope(decision) {
  if (!decision || typeof decision !== 'object') return { action: 'rerun_all' }
  if (decision.action === 'rerun_subset') {
    return {
      action: 'rerun_subset',
      stepIds: normalizeStrings(decision.stepIds),
      failedStepIds: normalizeStrings(decision.failedStepIds),
      affectedStepIds: normalizeStrings(decision.affectedStepIds),
    }
  }
  return {
    action: 'rerun_all',
    failedStepIds: normalizeStrings(decision.failedStepIds),
  }
}

function recordsForRerun(records, rerunScope) {
  if (!rerunScope || rerunScope.action !== 'rerun_subset') return records
  const allowed = new Set(normalizeStrings(rerunScope.stepIds))
  if (!allowed.size) return records
  return records
    .map((record) => {
      const steps = (record.steps || []).filter((step) => allowed.has(stepKey(step)))
      return Object.assign({}, record, { steps })
    })
    .filter((record) => record.steps.length)
}

async function stabilizeReviewCode(deps, workItem, context, retryState, aggregated, records) {
  const needsReview = fixBatches(retryState.fixBatchHistory).length > 0 ||
    (typeof deps.alwaysStabilizeReviewCode === 'function' && deps.alwaysStabilizeReviewCode())
  if (!needsReview && typeof deps.reviewCode !== 'function') {
    return { ok: true, changed: false, reviewCoverageHead: retryState.currentHead, verifyPassedHead: retryState.currentHead }
  }
  if (!needsReview && deps.requireReviewCode !== true) {
    return { ok: true, changed: false, reviewCoverageHead: retryState.currentHead, verifyPassedHead: retryState.currentHead }
  }
  if (retryState.reviewStabilizationCycle >= 2) {
    return { ok: false, reason: 'review-code stabilization cycle cap reached' }
  }
  if (typeof deps.reviewCode !== 'function') {
    return { ok: false, reason: 'review-code stabilization leaf unavailable' }
  }
  const cycle = (retryState.reviewStabilizationCycle || 0) + 1
  const before = retryState.currentHead
  let result
  try {
    result = await deps.reviewCode(workItem, {
      purpose: 'test-pilot-stabilization',
      worktree: context.worktree,
      expectedHead: before,
      runDirSuffix: `test-pilot-${cycle}-${before}`,
      cycle,
      browserFixBatchCount: fixBatches(retryState.fixBatchHistory).length,
      records,
      aggregated,
    })
  } catch (err) {
    return { ok: false, reason: `review-code stabilization failed: ${message(err)}` }
  }
  if (!result || result.ok === false || result.gate === 'changes-requested' ||
      (result.phaseResult && result.phaseResult.confidence === 'low')) {
    // #212: prefer the named parkDetail (e.g. "cannot-certify: <seat> ... (receipt-missing — …)") so
    // the stabilization park reason stays as honest as the workflow park, then assumptions[0], then generic.
    return { ok: false, reason: (result && (result.reason || (result.phaseResult && (result.phaseResult.parkDetail || (result.phaseResult.assumptions && result.phaseResult.assumptions[0]))))) || 'review-code stabilization parked' }
  }
  if (result.terminal === 'clean-with-skips') {
    return { ok: false, reason: 'review-code stabilization clean-with-skips produced no covers stamp' }
  }
  const after = result.head || result.headAfter || result.currentHead || before
  const changed = after !== before || result.changed === true || result.mutated === true
  return {
    ok: true,
    changed,
    head: after,
    reviewCoverageHead: result.reviewCoverageHead || result.covers || after,
    verifyPassedHead: result.verifyPassedHead || result.verifyHead || after,
  }
}

async function restoreFinalBaseline(deps, records, context, retryState) {
  if (typeof deps.restoreBaseline !== 'function') {
    return { ok: true, baseline: context.baseline || { head: retryState.currentHead, restored: true } }
  }
  try {
    const out = await deps.restoreBaseline(records, {
      context,
      head: retryState.currentHead,
      fixBatchHistory: retryState.fixBatchHistory,
      reviewStabilizationCycle: retryState.reviewStabilizationCycle || 0,
    })
    if (!out || out.ok === false || out.action === 'park' || out.confidence === 'low') {
      return { ok: false, reason: (out && out.reason) || 'final seed baseline restore parked' }
    }
    const baseline = out.baseline || out.status || out
    if (!coversHead(baseline, retryState.currentHead)) {
      return { ok: false, reason: 'final seed baseline restore did not verify the final head' }
    }
    return { ok: true, baseline }
  } catch (err) {
    return { ok: false, reason: `final seed baseline restore failed: ${message(err)}` }
  }
}

async function ensureFinalArtifacts(deps, payload) {
  if (typeof deps.ensureFinalArtifacts !== 'function') {
    return { ok: true, artifacts: payload.artifacts }
  }
  try {
    const out = await deps.ensureFinalArtifacts(payload)
    if (!out || out.ok === false || out.action === 'park' || out.confidence === 'low') {
      return { ok: false, reason: (out && out.reason) || 'final test-pilot results artifact parked' }
    }
    const artifacts = out.artifacts || out
    if (!artifacts.plan || !artifacts.results) {
      return { ok: false, reason: 'final test-pilot plan/results artifacts missing' }
    }
    return Object.assign({ ok: true, artifacts }, out)
  } catch (err) {
    return { ok: false, reason: `final test-pilot artifact publish failed: ${message(err)}` }
  }
}

async function publishFinalHead(deps, workItem, context, retryState, payload) {
  if (typeof deps.publishReady !== 'function') {
    return { ok: true, remotePr: context.remotePr || context.remotePR || { head: retryState.currentHead } }
  }
  try {
    const out = await deps.publishReady(workItem, retryState.currentHead, Object.assign({
      context,
      branch: context.branch,
      head: retryState.currentHead,
    }, payload))
    if (!out || out.ok === false || out.action === 'park' || out.confidence === 'low') {
      return { ok: false, reason: (out && out.reason) || 'final tested head publish parked' }
    }
    if (out.read_back === false) {
      return { ok: false, reason: (out && out.reason) || 'final tested head read-back mismatch' }
    }
    const remotePr = out.remotePr || out.remotePR || { branch: context.branch, head: out.head || retryState.currentHead }
    if (!coversHead(remotePr, retryState.currentHead)) {
      return { ok: false, reason: 'remote PR head does not equal final tested head' }
    }
    return { ok: true, remotePr }
  } catch (err) {
    return { ok: false, reason: `final tested head publish failed: ${message(err)}` }
  }
}

function coversHead(value, head) {
  if (!value || typeof value !== 'object') return false
  return value.head === head || value.covers === head || value.browserEvidenceHead === head
}

async function writeRetryStatus(deps, workItem, context, retryState, aggregated, records, reason) {
  return writeStatus(deps, workItem, milestoneStatus(context, workItem, 'browser-retry-parked', {
    planRecords: records,
    fixBatchHistory: retryState.fixBatchHistory,
    reviewStabilizationCycle: retryState.reviewStabilizationCycle || 0,
    browserEvidenceHead: retryState.browserEvidenceHead,
    lastBrowserResult: aggregated,
    reason,
  }))
}

function normalizeStrings(values) {
  if (!Array.isArray(values)) return []
  return values.map((value) => value == null ? '' : String(value)).filter(Boolean)
}

function normalizeShas(values) {
  return normalizeStrings(values)
}

function mergeAllowedSkippedResults(resultRecords, planRecords) {
  const records = resultRecords.map((record) => Object.assign({}, record))
  for (const planRecord of planRecords) {
    for (const step of planRecord.steps || []) {
      const skipped = step.status === 'skipped' || step.result === 'skipped'
      if (!skipped) continue
      records.push({
        stepId: stepKey(step),
        status: 'skipped',
        allowed: true,
        preserved: true,
        removalReason: step.removalReason,
        priorResult: step.priorResult,
        planContext: step.planContext,
        browserExecuted: true,
      })
    }
  }
  return records
}

function milestoneStatus(context, workItem, milestone, extra) {
  return Object.assign({
    schemaVersion: 1,
    verdict: 'park',
    milestone,
    workItem,
    branch: context.branch,
    head: context.head,
  }, extra || {})
}

async function callLeaf(fn, ...args) {
  if (typeof fn !== 'function') throw new Error('required leaf is unavailable')
  return fn(...args)
}

// Best-effort: stamp a parked status carrying WHY before an early low() return, so the mark-ready
// gate (and a human reading the sidecar) see the real cause instead of an opaque "status missing".
// Never changes the returned reason and never fails the phase if the write is unavailable/fails —
// the not_applicable path writes a status the same way; these early parks were the gap.
async function recordParkStatus(deps, workItem, context, reason) {
  if (!context) return
  try {
    await writeStatus(deps, workItem, milestoneStatus(context, workItem, 'parked', { reason }))
  } catch (_) { /* best-effort: low(reason) below still carries the real cause */ }
}

async function parkLow(deps, workItem, context, reason) {
  await recordParkStatus(deps, workItem, context, reason)
  return low(reason)
}

function low(reason) {
  return { confidence: 'low', assumptions: [reason] }
}

function message(err) {
  return err && err.message ? err.message : String(err || 'unknown')
}

module.exports = {
  testPilotPhase,
  collectAppBugFailures,
  dispatchFixBatch,
  ensureCleanWorktreeAfterFix,
  reconcileCommittedMutations,
  stabilizeReviewCode,
}

};

// ===== build_progress.js =====
__modules["build_progress"] = function (module, exports, require) {
// plugins/superheroes/lib/build_progress.js
function reconcile(taskList, committedTaskIds, unmappedCommits, reviewRecords, worktreeDirty, finalReview, provenance) {
  const committed = new Set(committedTaskIds || [])
  const reviews = reviewRecords || {}
  if (unmappedCommits && unmappedCommits > 0) {
    return { action: 'park', reason: `${unmappedCommits} commit(s) above the branch base carry no/unknown Task-Id — fail closed (UFR-7)` }
  }
  if (provenance === 'garbled') {
    return { action: 'park', reason: 'build provenance is unreadable (garbled) — fail closed (UFR-6)' }
  }
  let resume = null
  for (const t of taskList || []) {
    if (!(committed.has(t.id) && reviews[t.id] === 'passed')) { resume = t; break }
  }
  if (worktreeDirty) {
    return { action: 'reset_uncommitted', resume_at: resume, reason: 'uncommitted leftover changes — reset only those, then re-dispatch (UFR-12)' }
  }
  if (resume !== null) {
    if (committed.has(resume.id)) {
      return { action: 'review_task', resume_at: resume, reason: 'task implemented but not reviewed — keep the commit, take it up at review (UFR-7)' }
    }
    return { action: 'build_task', resume_at: resume, reason: 'first task not yet implemented — build it' }
  }
  if (finalReview === null || finalReview === undefined || !finalReview.clean) {
    return { action: 'final_review', reason: 'all tasks complete — run/resume the whole-branch final review to a clean result (FR-8/UFR-7)' }
  }
  if (provenance === 'absent') {
    return { action: 'write_provenance', reason: 'final review clean, provenance absent — (re)write provenance idempotently, do not re-review (FR-9)' }
  }
  return { action: 'complete', reason: 'build complete — provenance present over the handed-off commit' }
}
module.exports = { reconcile }

};

// ===== worker_recovery.js =====
__modules["worker_recovery"] = function (module, exports, require) {
// plugins/superheroes/lib/worker_recovery.js
// In-process twin of worker_recovery.py (#115 increment B) — byte-for-byte parity is CI-enforced
// (test_parity.py). Bounded build-worker recovery (UFR-3): (attempt, signal, maxAttempts) ->
// {action, reason} where action ∈ retry_with_context | escalate | park. A "plan is wrong" signal
// parks immediately; otherwise retry (early attempts), escalate on the attempt before the cap, then
// park at the cap.
const PLAN_WRONG = 'plan_wrong'
const DEFAULT_MAX_ATTEMPTS = 3

function decide(attempt, signal, maxAttempts = DEFAULT_MAX_ATTEMPTS) {
  if (signal === PLAN_WRONG) {
    return { action: 'park',
      reason: 'worker signalled the plan/task is wrong or too large — park (UFR-3)' }
  }
  if (attempt >= maxAttempts) {
    return { action: 'park',
      reason: `worker still blocked at the fixed maximum (${maxAttempts}) — park (UFR-3)` }
  }
  if (attempt === maxAttempts - 1) {
    return { action: 'escalate',
      reason: 'retry budget nearly spent — escalate to a more capable worker (UFR-3)' }
  }
  return { action: 'retry_with_context',
    reason: `worker needs more context — retry (attempt ${attempt} of ${maxAttempts})` }
}

module.exports = { decide, DEFAULT_MAX_ATTEMPTS, PLAN_WRONG }

};

// ===== task_review.js =====
__modules["task_review"] = function (module, exports, require) {
// plugins/superheroes/lib/task_review.js
// In-process twin of task_review.py (#115 increment B) — byte-for-byte parity is CI-enforced
// (test_parity.py). The BESPOKE two-verdict per-task review decision (FR-5/FR-6/FR-7, UFR-5), NOT
// routed through reviewPanel. Reuses only the loop primitives: circuit_breaker.BLOCKING (the
// Critical/Important set), circuit_breaker.checkCircuitBreaker, and loop_state.decide.
const circuitBreaker = require('./circuit_breaker.js')
const loopState = require('./loop_state.js')

const REQUIRED_VERDICTS = ['spec_compliance', 'code_quality']
// exit_skipped maps to PARK, never complete: a deliberately-left-unresolved blocker must park (UFR-4).
// (The bespoke loop passes skippedBlocking=0 so loop_state never returns exit_skipped today; the
// fail-closed mapping guards against a future contract change rather than fail open.)
const _MAP = { review: 'review', exit_clean: 'complete', exit_skipped: 'park', halt: 'park' }

function _partition(findings) {
  const blocking = []; const minors = []; const cannotVerify = []
  for (const f of findings || []) {
    if (f && f.cannot_verify_from_diff) cannotVerify.push(f)
    if (f && circuitBreaker.BLOCKING.has(f.severity)) blocking.push(f)
    else minors.push(f)
  }
  return { blocking, minors, cannotVerify }
}

function decide(verdicts, findings, rnd, maxRounds, history) {
  verdicts = verdicts || {}
  if (!REQUIRED_VERDICTS.every((k) => verdicts[k])) {
    return { action: 're_request', blocking: [], minors: [], cannot_verify: [],
      reason: 'both verdicts (spec-compliance + code-quality) are required (FR-5)' }
  }
  const { blocking, minors, cannotVerify } = _partition(findings)
  const rounds = (history || []).concat([{ round: rnd, findings: findings || [] }])
  const brk = circuitBreaker.checkCircuitBreaker(rounds, maxRounds)
  const [action, , loopReason] = loopState.decide(blocking.length, 0, rnd, maxRounds, !!brk.halt)
  let mapped = _MAP[action]
  let reason = loopReason
  if (brk.halt) {
    reason = brk.detail !== undefined ? brk.detail : reason
  }
  // UFR-5: never complete while a cannot-verify item is unresolved — force a resolution round.
  if (mapped === 'complete' && cannotVerify.length) {
    mapped = 'review'
    reason = "unresolved 'cannot verify from diff' item(s) must be confirmed, sent back, or parked (UFR-5)"
  }
  return { action: mapped, blocking, minors, cannot_verify: cannotVerify, reason }
}

module.exports = { decide }

};

// ===== engine_pref.js =====
__modules["engine_pref"] = function (module, exports, require) {
// engine_pref.js — twin of engine_pref.resolve_engine / resolve_effort.
// Pure + deterministic engine-preference resolver. Fail-OPEN to 'claude'.

const ENGINES = ['claude', 'codex', 'cursor']
const DEFAULT_STALL_LIMIT_SECONDS = 300

// `author-plan` (the front-half plan-author leaf) reads its OWN key — plan authoring routes
// independently of review/build; tasks authoring has no key on purpose and always runs native.
const _ROLE_KEY = { review: 'reviewer', build: 'implementation', fix: 'implementation',
  'author-plan': 'planAuthor' }
// Depth-aware review: deep reviewers (security/architecture — reviewer-deep tier) -> 'review-deep'
// (xhigh); regular review -> 'review' (high). Mirrors engine_pref.py._CODEX_EFFORT.
const _CODEX_EFFORT = { review: 'high', 'review-deep': 'xhigh', build: 'high', fix: 'low',
  'author-plan': 'xhigh' }
const _CURSOR_EFFORT = 'composer'

// Own-key membership (mirror model_tier.js): JS `in`/bracket walk the prototype chain,
// so a prototype-named engine/role ('constructor', 'toString') must not drift the result.
function hasOwn(o, k) {
  return Object.prototype.hasOwnProperty.call(o, k)
}

function resolveEngine(roleKind, prefs) {
  if (!hasOwn(_ROLE_KEY, roleKind)) return 'claude'
  const key = _ROLE_KEY[roleKind]
  if (!prefs || typeof prefs !== 'object' || Array.isArray(prefs)) return 'claude'
  if (!hasOwn(prefs, key)) return 'claude'
  const v = prefs[key]
  if (typeof v === 'string' && ENGINES.indexOf(v) !== -1) return v
  return 'claude'
}

function resolveEffort(engine, roleKind, overrides) {
  let def
  if (engine === 'codex') def = hasOwn(_CODEX_EFFORT, roleKind) ? _CODEX_EFFORT[roleKind] : 'high'
  else if (engine === 'cursor') def = _CURSOR_EFFORT
  else return null // claude or unknown engine
  if (overrides && typeof overrides === 'object' && !Array.isArray(overrides) && hasOwn(overrides, roleKind)) {
    const v = overrides[roleKind]
    if (typeof v === 'string' && v.trim()) return v.trim()
  }
  return def
}

// Twin of resolve_timeout: the finite UFR-5 stall limit. A valid positive int override wins; else the
// finite default. bool is excluded (JS has no int/bool subtype trap, but mirror the Python guard's intent:
// only a real positive integer number is honored). Always returns a finite positive int; never throws.
function resolveTimeout(overrides) {
  if (overrides && typeof overrides === 'object' && !Array.isArray(overrides) && hasOwn(overrides, 'timeout')) {
    const v = overrides.timeout
    if (typeof v === 'number' && Number.isInteger(v) && v > 0) return v
  }
  return DEFAULT_STALL_LIMIT_SECONDS
}

module.exports = { resolveEngine, resolveEffort, resolveTimeout, ENGINES, DEFAULT_STALL_LIMIT_SECONDS }

};

// ===== engine_dispatch.js =====
__modules["engine_dispatch"] = function (module, exports, require) {
// plugins/superheroes/lib/engine_dispatch.js
// Spine leaf wrapper (#38): the single seam every JS call site invokes instead of agent() when the
// engine is external (codex|cursor). Deterministic argv/parse/commit live in engine_adapter.py; this
// wrapper sequences them through the spine's exec dumb-pipe and returns the NATIVE result shape so
// everything downstream (loop math, verify gate, journal) is reused unchanged. Read roles are
// read-only (no preSHA/commit); write roles capture preSHA -> engine edits -> adapter commits.
const { libPath } = require('./lib_root.js')
const DEFAULT_STALL_LIMIT_SECONDS = 300   // UFR-5 finite default; test-settable via opts.timeoutSeconds

function shq(s) { return "'" + String(s).replace(/'/g, "'\\''") + "'" }

// Build a shell command that stages `content` to `path` via base64 (NOT a heredoc): external/engine
// text is untrusted and MAY contain a line identical to any fixed heredoc sentinel, which would
// terminate the heredoc early and corrupt the staged file. Encoding sidesteps sentinels entirely.
// Buffer is permitted in the bundle (the FR-8 static guard only bans a short list of non-deterministic
// or Node-only globals — the wall-clock/PRNG/filesystem/process APIs); base64 output is pure ASCII so
// shq's single-quote escaping is sufficient.
function _stageCmd(path, content) {
  const b64 = Buffer.from(content == null ? '' : String(content), 'utf8').toString('base64')
  return `printf %s ${shq(b64)} | base64 -d > ${shq(path)}`
}

// Reuse the spine's exec dumb-pipe (lazy require avoids a load-time cycle: showrunner requires the
// bundle graph; deferring keeps engine_dispatch's require surface minimal for the smokes).
let _execFn = null
function _exec(commands) {
  if (!_execFn) _execFn = require('./showrunner.js').exec
  return _execFn(commands)
}

// Run ONE command through the exec dumb-pipe and parse its JSON stdout. Mirrors the canonical
// build_phase.js:43-64 `execJson` contract: the cheap haiku courier occasionally drops/garbles a
// command's stdout even though it ran (live: a journal_entry.py leaf returned stdout:"" with ok:true,
// so JSON.parse("") threw and the build fail-closed-parked); retry ONCE on an empty or unparseable
// stdout before failing closed. The dispatch-path commands here (journal append, adapter build-argv /
// parse-result / commit, preSHA) are idempotent / harmless to repeat. Returns the parsed object, or
// null after the retry (the caller fails closed on null). A clean {"ok":true} on the first call returns
// immediately (one exec, no behavior change); a parseable {"ok":false} (a REAL durable-write failure)
// is returned as-is on the first call — it is NOT a courier-drop, so it is NOT retried.
async function _execJson(cmd) {
  for (let attempt = 0; attempt < 2; attempt++) {
    const res = await _exec([cmd])
    const r0 = res && res[0]
    if (r0 && r0.ok) {
      const s = (r0.stdout == null ? '' : String(r0.stdout)).trim()
      if (s) { try { return JSON.parse(s) } catch (_e) { /* garbled -> retry */ } }
      // empty stdout -> retry (courier likely dropped it)
    }
    // exec-level failure or empty/garbled -> retry once, then give up
  }
  return null
}

// preSHA capture for write roles — the established spine pattern (showrunner.js:1226).
async function _captureHead(wt) {
  const res = await _exec([`git -C ${shq(wt)} rev-parse HEAD`])
  const r0 = res && res[0]
  if (r0 && r0.ok) { const s = (r0.stdout == null ? '' : String(r0.stdout)).trim(); if (s) return s }
  return null
}

// Run the fully-formed external argv through exec, FEEDING the staged prompt file to the process
// stdin via a shell redirect. BOTH engines take the prompt on stdin: codex's trailing `-` reads
// stdin, and cursor-agent reads stdin when given no positional prompt. The argv tokens are
// shell-quoted so paths/effort strings can't break the command; the redirect is appended last so
// the prompt is always delivered (no </dev/null guard — there is always a prompt here).
// FR-8 confinement: the command is ALWAYS prefixed with `cd <cwd> && ` (mirroring showrunner.js's
// inWorktree()) so the external process runs rooted at the per-task build worktree — never at
// __SR_ROOT (the repo root selfContained() would otherwise apply via exec's dumb-pipe). This matters
// most for cursor, whose argv (engine_adapter.py) carries NO -C/cwd flag of its own; codex is
// self-confining via -C but the cd prefix is harmless/idempotent for it too. Applied unconditionally
// whenever a cwd is supplied (read roles are already read-only-sandboxed by the engine itself).
//
// FIX 2 (premortem): the JS Promise.race in dispatchExternal only stops US from WAITING on a stalled
// CLI — the subprocess itself keeps running unkilled, orphaned, potentially still writing to the
// worktree/git index while the caller has already fallen open and is retrying with the native Claude
// worker (a write-write race on the same files). Bound the CLI at the OS level too: wrap it with a
// portable `perl -e 'alarm shift @ARGV; exec @ARGV or exit 127'` — perl's alarm() SIGALRMs the process
// after <timeoutSeconds>, and since exec() replaces the perl process image with the CLI (same PID), the
// alarm fires against the CLI itself, killing it. This is belt-and-suspenders with the JS race (which
// stays, so a slow-to-signal-death CLI still can't hang the caller past limitMs) — the perl layer's job
// is only to make sure the CLI is actually DEAD, not just unwaited-on. perl/alarm/exec are ordinary CLI
// tokens (not Node/JS globals), so they don't trip the bundle's banned-global static check.
// Returns the raw stdout string (or null on fail).
async function _runArgv(argv, promptPath, cwd, timeoutSeconds) {
  const seconds = Number(timeoutSeconds) > 0 ? Math.ceil(Number(timeoutSeconds)) : Math.ceil(DEFAULT_STALL_LIMIT_SECONDS)
  const quotedArgv = argv.map((a) => shq(a)).join(' ')
  const alarmed = `perl -e ${shq("alarm shift @ARGV; exec @ARGV or exit 127")} ${seconds} ${quotedArgv}`
  const cmd = cwd ? `cd ${shq(cwd)} && ${alarmed} < ${shq(promptPath)}` : `${alarmed} < ${shq(promptPath)}`
  const res = await _exec([cmd])
  const r0 = res && res[0]
  if (r0 && r0.ok) return (r0.stdout == null ? '' : String(r0.stdout))
  return null
}

async function _journalExternal(payload) {
  // Journal the external action as a FIRST-CLASS `external_dispatch` event (FR-6): the audit line's
  // `type` is external_dispatch (Task 4 added the type + the journal_entry.py --event-type flag), and
  // the payload is written AS-IS (non-secret {engine,effort,roleKind,verify,outcome}). A failed durable
  // append -> {ok:false} -> the caller treats it as UFR-6 (fail-closed, unauditable).
  return _execJson(
    `python3 ${libPath('journal_entry.py')} --work-item ${shq(payload.workItem || '')} ` +
    `--event-type external_dispatch --payload ` +
    shq(JSON.stringify({ engine: payload.engine, effort: payload.effort, roleKind: payload.roleKind,
      verify: payload.verify, outcome: payload.outcome })))
}

// Scrub external-derived free-text (git stderr in a commit/dispatch-failure reason) BEFORE it enters
// an owner-facing notice — the band's single scrub seam (pr_comment.py scrub reads stdin -> scrubbed
// stdout, the same scrubber readout/parse_result use). On any exec/scrub failure fall back to a
// fixed generic label (never surface the raw external text). Only used on the failure/notice path.
async function _scrubReason(reason) {
  const s = reason == null ? '' : String(reason)
  if (!s) return s
  const res = await _exec([`printf '%s' ${shq(s)} | python3 ${libPath('pr_comment.py')} scrub`])
  const r0 = res && res[0]
  if (r0 && r0.ok && r0.stdout != null) return String(r0.stdout)
  return 'external error (scrubbed)'
}

// FIX 3: the body runs inside a try/catch in the exported dispatchExternal below, so ANY thrown
// error (a synchronous throw from a step here, or an unavailable Buffer/setTimeout global) still
// returns the native {ok:false} failure shape instead of throwing — callers' fall-open-to-Claude
// path (UFR-2 discard + native worker) only fires on a returned failure, never on an exception.
async function _dispatchExternalInner(o) {
  const { engine, roleKind, effort, prompt, cwd, schema, timeoutSeconds, model } = o
  const limitSeconds = Number(timeoutSeconds) > 0 ? Number(timeoutSeconds) : DEFAULT_STALL_LIMIT_SECONDS
  const limitMs = limitSeconds * 1000
  const isWrite = (roleKind === 'build' || roleKind === 'fix')
  // author-plan (the plan-author leaf) is write-SANDBOXED (it authors the doc + stamps the marker)
  // but takes NO preSHA/commit: definition-docs are not committed by the produce phase (native
  // authors don't commit either; in-repo docs ride the ship phase, out-of-repo docs never commit).
  // Its acceptance gate is the caller's deterministic usableDraft post-check, not this dispatch.
  const isAuthor = (roleKind === 'author-plan')

  // 1. Stage prompt + schema to disk (via exec). The PROMPT file is fed to the external process
  //    stdin by _runArgv (both engines read the prompt from stdin); the SCHEMA path is passed to
  //    build-argv via --schema-path (codex --output-schema for read roles).
  // runId is built from CALLER-SUPPLIED identifiers only — no wall-clock time or PRNG calls (FR-8:
  // the Workflow sandbox has no time/random globals, and the bundle-smoke statically bans those APIs
  // because they break deterministic resume). taskId (write roles) or workItem (read roles) plus
  // engine/roleKind give a stable-enough per-dispatch key; callers that omit both share a fallback
  // key, which is safe because writeInputs/rawPath are consumed synchronously within this single
  // dispatch and never read back across calls.
  const runKey = String(o.taskId || o.workItem || 'run').replace(/[^A-Za-z0-9_.-]+/g, '-').slice(0, 80)
  const runId = `${engine}-${roleKind}-${runKey}`
  const promptPath = `/tmp/engine-${runId}.prompt`
  const schemaPath = `/tmp/engine-${runId}.schema.json`
  const writeInputs = await _exec([
    _stageCmd(promptPath, prompt || ''),
    _stageCmd(schemaPath, JSON.stringify(schema || {})),
  ])
  if (!(writeInputs && writeInputs.every && writeInputs.every((r) => r && r.ok))) {
    return { ok: false, reason: 'could-not-stage-external-inputs' }
  }

  // 2. preSHA (write roles only — read roles never mutate the tree, FR-7).
  let preSha = null
  if (isWrite) {
    preSha = await _captureHead(cwd)
    if (!preSha) return { ok: false, reason: 'could-not-capture-preSHA' }
  }

  // 3. Wrap the whole dispatch in the UFR-5 finite timeout. A stall -> {ok:false, reason:'timeout'}.
  const run = (async () => {
    const argvObj = await _execJson(
      `python3 ${libPath('engine_adapter.py')} build-argv --engine ${shq(engine)} --role ${shq(roleKind)} ` +
      `--effort ${shq(String(effort == null ? '' : effort))} --cwd ${shq(cwd || '.')} ` +
      `--schema-path ${shq(schemaPath)}` +
      (typeof model === 'string' && model ? ` --model ${shq(model)}` : ''))
    const argv = argvObj && Array.isArray(argvObj.argv) ? argvObj.argv : (Array.isArray(argvObj) ? argvObj : null)
    if (!argv) return { ok: false, reason: 'build-argv-failed' }

    // Feed the staged prompt file to the external process stdin (the argv itself carries no prompt).
    // cwd is threaded through so _runArgv can confine the run to the worktree (FR-8; see _runArgv).
    // limitSeconds is threaded through so _runArgv can OS-level-kill a stalled CLI (FIX 2 below) —
    // the same value that bounds the JS Promise.race, so the perl alarm and the race agree.
    const rawStdout = await _runArgv(argv, promptPath, cwd, limitSeconds)
    if (rawStdout == null) return { ok: false, reason: 'external-run-failed' }

    // parse-result SCRUBS external free-text at the adapter boundary (Task 6); pass raw stdout by file.
    const rawPath = `/tmp/engine-${runId}.out`
    const wroteRaw = await _exec([_stageCmd(rawPath, rawStdout)])
    if (!(wroteRaw && wroteRaw[0] && wroteRaw[0].ok)) return { ok: false, reason: 'could-not-stage-external-output' }
    const parsed = await _execJson(
      `python3 ${libPath('engine_adapter.py')} parse-result --engine ${shq(engine)} --role ${shq(roleKind)} ` +
      `--stdout-path ${shq(rawPath)}`)
    if (!parsed || parsed.ok !== true) return { ok: false, reason: (parsed && parsed.reason) || 'unreadable' }
    return parsed
  })()

  let parsed
  // clearTimeout() the race's timeout handle once the race settles so a losing timer (the common
  // case: `run` settles first) never pins the process/test-runner event loop alive for up to
  // `limitMs` after this call already returned — pure Node hygiene, does not change the race's
  // outcome or timing. (Not unref()'d: unref would let the loop exit before EITHER branch fires
  // when the only other pending work is itself unref'd, silently abandoning the await.)
  let timeoutHandle = null
  try {
    parsed = await Promise.race([
      run,
      new Promise((resolve) => {
        timeoutHandle = setTimeout(() => resolve({ ok: false, reason: 'timeout' }), limitMs)
      }),
    ])
  } catch (_e) { parsed = { ok: false, reason: 'external-run-threw' } }
  finally { if (timeoutHandle) clearTimeout(timeoutHandle) }

  // 4a. Author role: no commit (see isAuthor above). Journal first (UFR-6 symmetry — an
  // unjournaled author dispatch is as unauditable as any other), then hand the parsed notify
  // back; the caller's usableDraft post-check decides acceptance and falls open on failure.
  if (isAuthor) {
    const jAuthor = await _journalExternal({ workItem: o.workItem, engine, effort, roleKind, verify: null,
      outcome: parsed.ok ? 'ok' : (parsed.reason || 'failed') })
    if (!(jAuthor && jAuthor.ok)) return { ok: false, reason: 'unauditable' }
    return parsed.ok ? { ok: true, notify: parsed.notify || [] } : { ok: false, reason: parsed.reason }
  }

  // 4. Read role: return findings straight through (no commit). Failure -> caller falls open to Claude.
  // FIX 5 (UFR-6 symmetry): a read role is JUST as unauditable as a write role when the journal
  // append itself fails — mirror the write-role check below (a failed journal -> {ok:false,
  // reason:'unauditable'}) instead of discarding the append's own success/failure unchecked.
  if (!isWrite) {
    const jRead = await _journalExternal({ workItem: o.workItem, engine, effort, roleKind, verify: null,
      outcome: parsed.ok ? 'ok' : (parsed.reason || 'failed') })
    if (!(jRead && jRead.ok)) return { ok: false, reason: 'unauditable' }
    return parsed.ok ? { findings: parsed.findings || [] } : { ok: false, reason: parsed.reason }
  }

  // 5. Write role failure -> only uncommitted edits exist; caller reuses resetUncommitted + falls open (UFR-2).
  if (!parsed.ok) {
    await _journalExternal({ workItem: o.workItem, engine, effort, roleKind, verify: null,
      outcome: parsed.reason || 'failed' })
    return { ok: false, reason: parsed.reason }
  }

  // 6. Write success -> the adapter is the SOLE committer (preSHA-scoped fold; single Task-Id trailer).
  const commit = await _execJson(
    `python3 ${libPath('engine_adapter.py')} commit --worktree ${shq(cwd)} --task-id ${shq(o.taskId || '')} ` +
    `--pre-sha ${shq(preSha)}`)
  if (!commit || commit.ok !== true) {
    // M1: commit.error carries raw git stderr — SCRUB it before it can reach an owner-facing notice.
    const reason = (commit && commit.error) ? await _scrubReason(commit.error) : 'commit-failed'
    // sec-101: the engine DID run and edited the worktree here, so this outcome must ALSO leave exactly
    // one audit line — otherwise commit-failure is the single external-dispatch outcome with no journal
    // entry (FR-6/UFR-6 symmetry gap). Journal BEFORE returning; the reason is already scrubbed above.
    await _journalExternal({ workItem: o.workItem, engine, effort, roleKind, verify: null,
      outcome: 'commit-failed' })
    return { ok: false, reason }
  }

  // 7. Journal BEFORE returning the native worker shape (UFR-6: unauditable -> the caller fails closed).
  const j = await _journalExternal({ workItem: o.workItem, engine, effort, roleKind,
    verify: 'pending', outcome: 'ok' })
  if (!(j && j.ok)) return { ok: false, reason: 'unauditable' }
  return { ok: true, signal: parsed.signal || 'ok', evidence: parsed.evidence || {} }
}

// FIX 3 (premortem): a synchronous throw ANYWHERE in the dispatch body (a bad destructure, an
// unavailable Buffer/setTimeout global, an unexpected exec-shape) must still resolve to the native
// {ok:false} failure shape — never throw out of dispatchExternal. Callers rely on a returned
// failure to trigger their fall-open-to-Claude path (UFR-2 resetUncommitted + native worker); an
// uncaught throw here would instead propagate up and abort the whole run.
async function dispatchExternal(o) {
  try {
    return await _dispatchExternalInner(o || {})
  } catch (_e) {
    return { ok: false, reason: 'dispatch-error' }
  }
}

module.exports = { dispatchExternal, DEFAULT_STALL_LIMIT_SECONDS }

};

// ===== build_phase.js =====
__modules["build_phase"] = function (module, exports, require) {
// plugins/superheroes/lib/build_phase.js
// The native "workhorse" build phase (#87). CONTROL FLOW ONLY: this module detects events and
// sequences them — it makes NO judgement inline. #115: every judgement is an in-process parity-locked
// JS twin (model_tier / worker_recovery / task_review / build_progress.reconcile); every IO/side-effect
// runs through the exec(raw)+in-process-parse dumb pipe, parsed deterministically and fail-closed (the
// old "trust-the-leaf-JSON" *_cli.py bridge is gone). It makes NO PR/merge/force-push (FR-10).
// FR-4a (#115): build state lives in memory during a continuous run. build_state gather /
// build_progress.reconcile are called ONLY on entry/resume (not per loop iteration).
const { reviewPanel } = require('./review_panel_shell.js')
const { io } = require('./io_seam.js')
const modelTierTwin = require('./model_tier.js')
const courier = require('./courier_exec.js')
// #115 increment B: the two SMART judgement leaves (worker_recovery, task_review) are now
// parity-locked in-process twins (no leaf — judgments live in twins, called in-process). Pure
// deciders with no IO, so a top-level require is safe (no load-time cycle).
const workerRecoveryTwin = require('./worker_recovery.js')
const taskReviewTwin = require('./task_review.js')
// #160: the blocking-severity set (Critical/Important) — the single source of truth the task_review
// twin's partition also reads. Used to synthesize the per-task review's two verdicts from an external
// engine's findings-only result (below). Pure module, safe to require at top level (no load-time cycle).
const circuitBreaker = require('./circuit_breaker.js')
// #38 Task 11: the engine-axis resolver twin + the spine leaf wrapper that dispatches external
// engines (codex|cursor) for the write (build|fix) and read (review) roles.
const engineDispatch = require('./engine_dispatch.js')
const enginePrefTwin = require('./engine_pref.js')

// #170: compose the spine CODE root (plugin-cache lib dir, or the repo-relative default) at
// CALL time — never a module-load const, since the bundle ENTRY plants __SR_LIB after factories.
const { libPath, libRoot } = require('./lib_root.js')
const MAX_ROUNDS = 3                 // per-task + final-review fix bound (plan: same bound as a task)

function shq(s) { return "'" + String(s).replace(/'/g, "'\\''") + "'" }

// #150: task-scoped leaf labels for the /workflows progress view (spaces, not kebab-case).
function implementTaskLabel(task, taskCount) {
  return `implement task ${task.id} of ${taskCount}`
}

function fixTaskLabel(task) {
  return `fix task ${task.id}`
}

function reviewTaskLabel(task, round) {
  return `review task ${task.id}:r${round}`
}
function park(reason) { return { confidence: 'low', assumptions: [reason], parkReason: reason } }
function ok() { return { confidence: 'high', assumptions: [] } }

// FR-8: the configured base (--base) arg, threaded into EVERY build_state_cli gather so the entry
// gather and the per-task UFR-7 check measure against the same base. Extracted to one helper so the
// two call sites can't drift (the live bug: the per-task check omitted --base and parked off a
// non-main base). Empty string when globalThis.__SR_BASE is unset -> byte-identical to today.
function baseArg() {
  const b = (typeof globalThis !== 'undefined' && globalThis.__SR_BASE) ? String(globalThis.__SR_BASE) : null
  return b ? ` --base ${shq(b)}` : ''
}

// Reuse the spine's proven exec primitive (lazy require avoids a load-time cycle: showrunner's
// build_phase reference is itself lazy, and deferring keeps build_phase's require surface unchanged
// for the smokes). One exec, no duplication, no front-half change.
let _execFn = null
function exec(commands, label) {
  if (!_execFn) _execFn = require('./showrunner.js').exec
  return _execFn(commands, label)
}

// Run ONE command via the exec dumb-pipe and parse its JSON stdout. The cheap haiku courier
// occasionally drops/garbles a command's stdout even though it ran (live: a journal_entry.py leaf
// returned stdout:"" with ok:true, so JSON.parse("") threw and the build fail-closed-parked); retry
// ONCE on an empty or unparseable stdout before failing closed. Build-path commands are idempotent /
// harmless to repeat (journal append, gate set, provenance, lease renew, gather/read).
// Returns the parsed object, or null after the retry (the caller fails closed on null — same
// park/false/fallback it produces today). A clean {"ok":true} on the first call returns immediately
// (one exec, no behavior change); a parseable {"ok":false} (a REAL durable-write failure) is returned
// as-is on the first call — it is NOT a courier-drop, so it is NOT retried.
// `label` is the cosmetic display purpose (defaults to 'exec'); dumb-pipe routing rides the courier's
// `courier: true` marker, so a descriptive label never loosens the cheapest-model pinning.
async function execJson(cmd, label) {
  try {
    return await courier.runCourierJson(label || 'exec', cmd)
  } catch (e) {
    if (e instanceof courier.CourierTransportError) return null
    throw e
  }
}

// Like execJson but for commands whose stdout is a PLAIN STRING (e.g. read-gate prints `passed`).
// Retry once on an empty stdout; returns the trimmed string, or null after the retry.
async function execText(cmd, label) {
  try {
    return (await courier.runCourierText(label || 'exec', cmd)).trim()
  } catch (e) {
    if (e instanceof courier.CourierTransportError) return null
    throw e
  }
}

// build_progress.reconcile via the module (NOT a destructured load-time binding) so reconcileState
// calls THROUGH the module export — keeps the twin the single source AND makes it spy-able in smokes
// (a testability improvement; the FR-4a entry-once property is re-asserted by spying reconcile).
function _reconcile(...a) { return require('./build_progress.js').reconcile(...a) }

// model_tier overrides: mirror showrunner.js's authorModel — read from globalThis.__SR_OVERRIDES
// (set by the Task 17 startup pipe; absent in test/throwaway runs -> null -> DEFAULT_TIERS).
function _overrides() { return (typeof globalThis !== 'undefined' && globalThis.__SR_OVERRIDES) || null }

// engine prefs: mirror _overrides — read from globalThis.__SR_ENGINE_PREFS (planted by the Task-12
// startup pipe; absent in test/throwaway runs -> both 'claude' -> the native agent() path, UNCHANGED).
function _enginePrefs() {
  const p = (typeof globalThis !== 'undefined' && globalThis.__SR_ENGINE_PREFS) || null
  return (p && typeof p === 'object') ? p : { reviewer: 'claude', implementation: 'claude', effort: {} }
}

// FR-9 effort overrides: the effort sub-map keyed by role_kind {review,build,fix} lives INSIDE the
// engine-prefs object (NOT the model-tier __SR_OVERRIDES map). resolveEffort reads this map; absent -> null.
function _effortOverrides() {
  const p = _enginePrefs()
  return (p && p.effort && typeof p.effort === 'object' && !Array.isArray(p.effort)) ? p.effort : null
}

// #115 increment B: cmdRunner is gone. The IO/side-effect leaves are ported to exec(raw)+in-process
// -parse (increment A); the two SMART judgement leaves (worker_recovery, task_review) are now
// parity-locked in-process twins (above) — no JS<->Python bridge remains in this module.

// FR-4a: gather authoritative git state (entry/resume only, NOT per loop iteration).
// Ported to exec(raw)+in-process-parse: the leaf runs the command and returns its raw stdout; the
// spine JSON.parses it here (the leaf can no longer derail by mis-copying fields — the live bug).
// Returns the parsed state object on success; NULL on exec-fail / parse-fail (the caller parks
// honestly); or {__error: <reason>} when the leaf emitted a STRUCTURED base-resolution error on
// stdout (C-I3) so the caller can park with THAT specific reason instead of the generic one.
// FR-8: thread configurable base (--base) when globalThis.__SR_BASE is set; absent -> _base() detection.
async function gatherState(workItem, branch, validIds, wt) {
  let parsed = null
  try {
    parsed = await courier.runCourierJson(
      'gather build state',
      `python3 ${libPath('build_state_cli.py')} gather --work-item ${shq(workItem)} --branch ${shq(branch)} --valid-ids ${shq(validIds)} --worktree ${shq(wt)}${baseArg()}`,
      {},
    )
  } catch (_) {
    parsed = null
  }
  if (parsed == null) return null
  // Structured fail-closed signal: the leaf could not resolve --base. Surface the SPECIFIC reason
  // (C-I3) rather than collapsing to the generic "could not gather authoritative git state" park.
  if (parsed && typeof parsed === 'object' && typeof parsed.error === 'string') {
    return { __error: parsed.error }
  }
  return parsed
}

// FR-4a: derive the starting action + resume_at from authoritative state using the in-process twin.
// Returns the reconcile decision object ({action, resume_at?, reason?}). Calls THROUGH the module
// export (_reconcile) so the twin stays the single source and is spy-able in smokes.
function reconcileState(taskList, state) {
  return _reconcile(
    taskList,
    state.committed_task_ids || [],
    state.unmapped_commits || 0,
    state.review_records || {},
    !!(state.worktree_dirty),
    state.final_review || null,
    state.provenance || null)
}

async function buildPhase(workItem, generation) {
  const root = '$(git rev-parse --show-toplevel)'
  // UFR-1: refuse unless the tasks gate is passed. read-gate prints a PLAIN STRING (e.g. 'passed'),
  // NOT JSON — execText returns the trimmed raw stdout (no JSON.parse), retrying the courier ONCE on
  // an empty stdout (a courier-drop) before failing closed. null -> park (fail closed on exec-fail).
  const gate = await execText(
    `python3 ${libPath('definition_doc.py')} read-gate --doc tasks --work-item ${shq(workItem)} --root "${root}"`,
    'read gate',
  )
  if (gate == null) return park('could not read the tasks gate — failing closed')
  if (gate !== 'passed') return park(`tasks gate not passed (${gate}) — refusing to build (UFR-1)`)
  // UFR-2: setup the content-addressed worktree/branch + persist this run's generation.
  const setup = await execJson(
    `python3 ${libPath('build_entry.py')} --work-item ${shq(workItem)} --generation ${shq(String(generation))}`,
    'prepare build',
  )
  if (setup == null) return park('build setup failed: no branch')
  if (!setup.branch) return park('build setup failed: ' + (setup.error || 'no branch'))
  const branch = setup.branch
  // The build branch is checked out in a SEPARATE managed build worktree (build_entry -> buildtree);
  // every git read/write below must operate there, not in the showrunner's main checkout.
  const wt = setup.path
  // UFR-8: zero executable tasks -> finish without building.
  // With exec+JSON.parse the BUG-2 string-recovery is structurally moot, but KEEP the
  // typeof===string JSON.parse recovery + Array.isArray guard as defense-in-depth (BUG-3).
  const _taskResult = await execJson(`python3 ${libPath('task_list_cli.py')} --work-item ${shq(workItem)}`, 'read tasks')
  if (_taskResult == null) return park('task-list command did not run — failing closed')
  let tasks = _taskResult.tasks
  if (typeof tasks === 'string') {
    try { tasks = JSON.parse(tasks) } catch (_) { tasks = null }
  }
  if (!Array.isArray(tasks)) return park('task-list returned non-array tasks — schema mismatch, failing closed')
  // Silent-zero guard: if the doc has raw task headings but the parser returned nothing,
  // the format is wrong (e.g. em-dash in an old doc not yet re-authored). Park explicitly
  // instead of silently finishing (which would be a UFR-8 bypass — building nothing when
  // there are tasks to build). raw_task_heading_count===0 is the genuine empty case.
  const rawHeadingCount = typeof _taskResult.raw_task_heading_count === 'number' ? _taskResult.raw_task_heading_count : 0
  if (tasks.length === 0 && rawHeadingCount > 0) {
    return park('tasks doc present but no parseable ### Task N: headings — format mismatch, refusing to build nothing')
  }
  if (tasks.length === 0) { log('no tasks to build'); return ok() }

  const validIds = tasks.map((t) => t.id).join(',')

  // FR-4a: gather authoritative git state ONCE at entry (not per iteration).
  // A fresh invocation (after park/crash) re-gathers here — resume correctness preserved.
  // gatherState returns null on exec/parse failure — park honestly (fail closed; never walk on a
  // mis-read or absent git state — the live bug that mis-reported a clean tree as dirty).
  let state = await gatherState(workItem, branch, validIds, wt)
  if (state && state.__error) return park(state.__error)
  if (!state) return park('could not gather authoritative git state — failing closed')

  // Handle entry-level non-forward reconcile actions before entering the forward-walk.
  // reset_uncommitted: fence, reset, then re-gather + re-reconcile ONCE (a reset is resume-like).
  let d = reconcileState(tasks, state)
  if (d.action === 'park') return park(d.reason || 'build_progress parked at entry')
  if (d.action === 'reset_uncommitted') {
    if (!(await fenceOrPark(workItem, generation))) return park('lease lost before reset — park (UFR-10)')
    const rr = await resetUncommitted(wt, branch)
    if (!rr.ok) return park('could not reset uncommitted changes: ' + (rr.error || 'unknown'))
    // Re-gather + re-reconcile after reset (ground truth mutated).
    state = await gatherState(workItem, branch, validIds, wt)
    if (state && state.__error) return park(state.__error)
    if (!state) return park('could not gather authoritative git state — failing closed')
    d = reconcileState(tasks, state)
    if (d.action === 'park') return park(d.reason || 'build_progress parked after reset')
    // If the SECOND reconcile is STILL reset_uncommitted, the reset did not fully clean the worktree.
    // Park honestly — bounded, fail-closed — rather than fall through into a dirty forward-walk
    // (#115 final review FIX 4 / UFR-12). One reset attempt only; a still-dirty tree is the owner's.
    if (d.action === 'reset_uncommitted') return park('worktree still dirty after reset — park (UFR-12)')
  }

  // FR-4a forward-walk: in-memory state for the continuous run.
  // Seed from the entry gather; advance only on confirmed durable success.
  const builtTaskIds = new Set(state.committed_task_ids || [])
  const reviewRecords = Object.assign({}, state.review_records || {})
  // Track whether THIS walk built or reviewed any task. If it did, the branch HEAD changed, so the
  // ENTRY gather's final_review.clean / provenance are STALE — the whole-branch final review must
  // RE-RUN over the new HEAD and provenance must be RE-WRITTEN. A pure resume (nothing built this
  // walk) keeps the skip optimization (the entry state is fresh). (#115 final review FIX 3 / FR-4a.)
  let didWork = false
  // Determine the starting index from the entry reconcile's resume_at.
  const resumeTaskId = d.resume_at ? d.resume_at.id : null

  // Forward-walk states that are already-past (handled after all-tasks-built+reviewed):
  // final_review, write_provenance, complete are processed after the task loop.
  // If the entry action indicates we're already past the task loop, skip it.
  const pastTaskLoop = (d.action === 'final_review' || d.action === 'write_provenance' || d.action === 'complete')

  if (!pastTaskLoop) {
    // Guard: bound so a non-progressing forward-walk can't spin forever.
    const MAX_GUARD = tasks.length * 4 + 8
    let guard = 0
    // Find the start index (resume from the first un-built or un-reviewed task).
    let startIdx = 0
    if (resumeTaskId !== null) {
      const idx = tasks.findIndex((t) => t.id === resumeTaskId)
      if (idx >= 0) startIdx = idx
    }

    for (let i = startIdx; i < tasks.length; i += 0) {
      guard += 1
      if (guard > MAX_GUARD) {
        return park('build loop exceeded its guard bound without completing (last task: '
          + (tasks[i] ? tasks[i].id : '?') + ')')
      }
      const task = tasks[i]
      const isBuilt = builtTaskIds.has(task.id)
      const isReviewed = reviewRecords[task.id] === 'passed'

      if (isBuilt && isReviewed) {
        // Already done in memory; advance.
        i += 1; continue
      }
      if (!isBuilt) {
        // Build the task (fence, dispatch worker, commit, journal, then review).
        const r = await buildOneTask(workItem, generation, task, branch, validIds, wt, tasks.length)
        if (r.parked) return park(r.reason)
        // On confirmed success (buildOneTask only returns !parked when journal+review both passed):
        builtTaskIds.add(task.id)
        reviewRecords[task.id] = 'passed'
        didWork = true                 // HEAD moved this walk -> entry final_review/provenance stale
        i += 1; continue
      }
      if (isBuilt && !isReviewed) {
        // Task implemented but not reviewed (e.g. after a crash mid-review): review it.
        const r = await reviewOneTask(workItem, generation, task, branch, wt)
        if (r.parked) return park(r.reason)
        reviewRecords[task.id] = 'passed'
        didWork = true                 // a review (with its possible fix commits) also moves HEAD
        i += 1; continue
      }
    }
  }

  // All tasks built+reviewed. Run the whole-branch final review.
  // Skip ONLY on a pure resume (didWork === false): the entry final_review.clean then covers the
  // current HEAD. If this walk built/reviewed anything, HEAD moved — the entry's final_review.clean
  // is STALE, so RE-RUN the whole-branch final review over the new HEAD (#115 final review FIX 3).
  const alreadyFinalClean = !didWork && state.final_review && state.final_review.clean
  if (!alreadyFinalClean) {
    const fr = await runFinalReview(workItem, generation, branch, wt)
    // UFR-4 fail-closed intent: only a 'clean' terminal advances. Parking on
    // 'clean-with-skips'/'halted'/'cannot-certify' is deliberate — a skipped blocker must park.
    if (fr.terminal !== 'clean') return park('whole-branch final review did not reach clean: ' + fr.terminal)
    const coverage = await recordFinalReviewClean(workItem)
    if (!(coverage && coverage.ok === true && coverage.read_back === true)) {
      return park('final review coverage stamp failed read-back')
    }
  }

  // Write provenance if absent (FR-9): idempotent, only after final review clean. Same staleness
  // guard: a walk that did work must RE-WRITE provenance over the new HEAD (don't trust the entry's).
  const alreadyProv = !didWork && state.provenance && state.provenance !== 'absent'
  if (!alreadyProv) {
    const p = await writeProvenance(workItem)
    if (!p.ok) return park('provenance not recorded: ' + (p.error || 'unknown'))
  }

  return ok()
}

// Reset ONLY uncommitted/untracked changes; never discard a commit (UFR-12). Returns {ok,error?}
// so a failed reset parks honestly (UFR-6) rather than spinning to the guard bound.
async function resetUncommitted(wt, branch) {
  // dumb pipe (fixed git commands, echo ok): courier:true so the bundle preamble pins it to the
  // cheapest model (#118 — an unmarked label inherits the session model).
  return agent(
    `In the build worktree at ${wt} (branch ${branch}), reset only uncommitted state: `
    + `git checkout -- . && git clean -fd . — do NOT touch any commit. `
    + `Return JSON {"ok":true} on success or {"ok":false,"error":"<reason>"}.`,
    { label: 'reset-uncommitted', courier: true, schema: { type: 'object', required: ['ok'], properties: { ok: {}, error: { type: 'string' } } } })
}

// Record build provenance once over HEAD = X (FR-9), via the existing prov_entry leaf.
// exec/parse fail -> {ok:false, error:'provenance leaf did not run'} so the caller's !p.ok parks.
async function writeProvenance(workItem) {
  // execJson retries the courier ONCE on a dropped/garbled stdout; null -> the SAME fail-closed
  // fallback as today ({ok:false} -> caller parks). A parseable {ok:false} is returned as-is (no retry).
  const r = await execJson(`python3 ${libPath('prov_entry.py')} --step build --work-item ${shq(workItem)}`, 'write provenance')
  if (r == null) return { ok: false, error: 'provenance leaf did not run' }
  return r
}

// Record final-review-clean. Caller does not check .ok today (preserve that), but stay fail-closed-safe.
async function recordFinalReviewClean(workItem) {
  try {
    return await courier.runCourierJson(
      'stamp build coverage',
      `python3 ${libPath('build_state_cli.py')} record-final-review --work-item ${shq(workItem)} --clean true`,
      { require: ['ok', 'read_back'], retryRealFailure: false },
    )
  } catch (_e) {
    return { ok: false, read_back: false }
  }
}

// fenceOrPark: lease-fence acquire. CRITICAL fail-closed: an exec/parse failure must read as a LOST
// fence (false), NEVER as ok — a fence failure read as ok would let an unfenced write through (UFR-10).
function _checkoutRoot() {
  const r = (typeof globalThis !== 'undefined' && globalThis.__SR_ROOT)
    ? String(globalThis.__SR_ROOT) : null
  return (r && r.trim()) ? r : null
}
async function fenceOrPark(workItem, generation) {
  const root = _checkoutRoot()
  if (!root) return false
  const f = await execJson(
    `python3 ${libPath('fence_cli.py')} --work-item ${shq(workItem)} --generation ${shq(String(generation))} --root ${shq(root)}`,
    'fence lease',
  )
  return !!(f && f.ok)
}

async function recordTaskBuilt(workItem, taskId) {
  try {
    return await courier.runCourierJson(
      'record task built',
      `python3 ${libPath('build_state_cli.py')} record-built --work-item ${shq(workItem)} --task ${shq(taskId)}`,
      { require: ['ok', 'read_back', 'task'], retryRealFailure: false },
    )
  } catch (_e) {
    return null
  }
}

async function recordTaskReviewed(workItem, taskId) {
  try {
    return await courier.runCourierJson(
      'record task reviewed',
      `python3 ${libPath('build_state_cli.py')} record-reviewed --work-item ${shq(workItem)} --task ${shq(taskId)}`,
      { require: ['ok', 'read_back', 'task'], retryRealFailure: false },
    )
  } catch (_e) {
    return null
  }
}

// UFR-4 run-time write preflight — cache the verdict for the whole run so we probe the host's
// autoMode.allow grant ONCE (not per task). null = not yet probed. The probe runs the engine's OWN
// write command inside the worktree; a denied/failed grant -> the impl role falls open to Claude.
let _writeAuthOk = null
let _writeAuthNotified = false
async function _implWriteAuthorized(engine, wt) {
  if (_writeAuthOk !== null) return _writeAuthOk
  const v = await execJson(
    `python3 ${libPath('engine_authz.py')} test-dispatch --engine ${shq(engine)} --cwd ${shq(wt)}`, 'check write auth')
  _writeAuthOk = !!(v && v.ok === true)
  if (!_writeAuthOk && !_writeAuthNotified) {
    _writeAuthNotified = true
    try { log(`build: ${engine} is not authorized to write in this run (autoMode.allow not granted) — the implementation role falls open to Claude for the whole run (UFR-4)`) } catch (_) {}
  }
  return _writeAuthOk
}

// Route the write role (build|fix) to the chosen implementation engine. claude -> the existing agent()
// path, BYTE-UNCHANGED. external -> dispatchExternal; on ANY non-success reset uncommitted edits (UFR-2)
// and fall open to the native agent() (UFR-1). preSHA/commit-discipline live inside dispatchExternal.
async function _implDispatch({ workItem, roleKind, taskId, prompt, wt, branch, nativeAgentCall }) {
  const engine = enginePrefTwin.resolveEngine(roleKind, _enginePrefs())
  if (engine === 'claude') return nativeAgentCall()
  // UFR-4: before the FIRST external WRITE, confirm the host grants this engine write authority.
  // Denied -> fall open to Claude for the whole run (build AND fixes) + one notice. Read roles skip this.
  if (!(await _implWriteAuthorized(engine, wt))) return nativeAgentCall()
  // FR-9: effort override comes from the engine-prefs effort sub-map (keyed by role_kind), NOT the
  // model-tier _overrides() map (keyed by role->model — resolveEffort could never match it).
  const effort = enginePrefTwin.resolveEffort(engine, roleKind, _effortOverrides())
  const res = await engineDispatch.dispatchExternal({
    engine, roleKind, effort, prompt, cwd: wt, schema: { type: 'object', required: ['ok'] },
    taskId, workItem,
  })
  if (res && res.ok) return res
  // UFR-2: a failed/stalled external write left only uncommitted edits -> discard, then redo on Claude.
  await resetUncommitted(wt, branch)
  try { log(`build: ${engine} ${roleKind} did not complete (${(res && res.reason) || 'unknown'}) — falling open to Claude`) } catch (_) {}
  return nativeAgentCall()
}

// #222: the mode-aware ABSOLUTE tasks-doc path. Reuses showrunner.docPathFor (the single source of
// truth — docDirFor reads the startup-planted __SR_DOC_DIRS, honoring out-of-repo storage, and falls
// back to the in-repo default when unplanted). Resolved at CALL time via the same lazy showrunner
// require as exec() above, so the pointer the worker gets is byte-identical to the spine's own.
function _tasksDocPath(workItem) {
  return require('./showrunner.js').docPathFor(workItem, 'tasks')
}

// #222: the per-task build prompt. Carries the ABSOLUTE tasks-doc pointer so the worker implements the
// task's real definition (not the one-line title) and never sweeps the owner's filesystem hunting for
// the doc — the out-of-repo-storage blind-build defect where a bare-main build worktree gave the worker
// nothing to anchor to (which also tripped repeated macOS TCC dialogs, live run 8). `retryNote` is
// appended ONLY on a re-dispatch so a needs_context retry is genuinely different from the first prompt.
function buildTaskPrompt(task, branch, wt, docPath, retryNote) {
  return (
    `In the build worktree at ${wt} (branch ${branch}), implement Task ${task.id} (${task.title}) TEST-FIRST: `
    + `write the test(s), run to observe FAIL, implement, run to observe PASS. The task's full definition is `
    + `Task ${task.id} in ${docPath} — Read it before writing code; implement THAT, not the title. Never search `
    + `the filesystem outside the build worktree and the given doc path. Commit with a trailer line `
    + `"Task-Id: ${task.id}" on EVERY commit you make for this task. Put the Task-Id: ${task.id} trailer in the `
    + `FINAL paragraph of the commit message with no blank line between it and any other trailer (e.g. `
    + `Co-Authored-By). Return JSON `
    + `{"ok":bool,"signal":"ok|needs_context|plan_wrong","evidence":{"testFailed":bool,"testPassed":bool}}.`
    + (retryNote || '')
  )
}

// #222: genuine added context on a needs_context re-dispatch — the worker signalled it lacked context,
// so escalate: name the absolute doc path again and instruct it to Read that exact section. Before this
// the recovery twin re-dispatched the byte-identical prompt and never added anything (UFR-3 retry).
function buildRetryNote(task, docPath) {
  return (
    ` RETRY — you signalled you were missing context. The full definition of Task ${task.id} is in ${docPath}: `
    + `open it with Read and implement that checkbox section exactly. Do not proceed from the title, and do not `
    + `search the filesystem outside the build worktree and that doc path.`
  )
}

// Build one task test-first (FR-3) with bounded recovery (UFR-3), then review it. `validIds` is the
// FULL enumeration's task ids (comma-joined) so the write-time trailer check scores every above-base
// commit against the whole task set — not just this task (an earlier task's commit is not "unmapped").
async function buildOneTask(workItem, generation, task, branch, validIds, wt, taskCount) {
  const docPath = _tasksDocPath(workItem)   // #222: anchor the worker to the real task definition
  let attempt = 1
  for (;;) {
    if (!(await fenceOrPark(workItem, generation))) {
      return { parked: true, reason: 'lease lost before build — park (UFR-10)' }
    }
    // #222: after the first attempt, add genuine context (re-state the doc path + a Read instruction)
    // so a needs_context retry is NOT the identical prompt the recovery twin used to re-dispatch.
    const prompt = buildTaskPrompt(task, branch, wt, docPath, attempt > 1 ? buildRetryNote(task, docPath) : '')
    const worker = await _implDispatch({
      workItem, roleKind: 'build', taskId: task.id, wt, branch,
      prompt,
      nativeAgentCall: () => agent(
        prompt,
        { label: implementTaskLabel(task, taskCount), schema: { type: 'object', required: ['ok'] } }),
    })
    if (worker.ok) {
      // write-time trailer enforcement (UFR-7): every above-base commit must carry its Task-Id.
      // This is a per-built-task CORRECTNESS read (NOT the FR-4a per-iteration resume gather).
      // execJson retries the courier ONCE on a dropped/garbled stdout, then fails closed: a leaf that
      // can't run / returns unparseable output must NOT read as a clean trailer state — park (UFR-7).
      const chk = await execJson(
        `python3 ${libPath('build_state_cli.py')} gather --work-item ${shq(workItem)} --branch ${shq(branch)} --valid-ids ${shq(validIds)} --worktree ${shq(wt)}${baseArg()}`,
        'check trailers',
      )
      if (chk == null) return { parked: true, reason: 'could not verify commit trailers — failing closed (UFR-7)' }
      // A structured base-resolution error (C-I3) must park with its specific reason, not slip past
      // the unmapped check below (where {error} has no unmapped_commits and would read as clean).
      if (typeof chk.error === 'string') return { parked: true, reason: chk.error }
      if ((chk.unmapped_commits || 0) > 0) {
        return { parked: true, reason: 'a commit lacks its Task-Id trailer — park (UFR-7)' }
      }
      // record-before-advance: journal must succeed before the task counts as built. Guard the .ok
      // explicitly (defense-in-depth for invariant #4): a failed journal must NOT advance into the
      // review loop — park honestly (#115 final review FIX 8). The FR-4a forward-walk no longer
      // self-heals a missed journal per-iteration, so this guard is the advance fence.
      // execJson retries the courier ONCE on a dropped/garbled stdout (the OBSERVED live failure: the
      // courier returned stdout:"" though the journal wrote, so JSON.parse("") threw and the build
      // parked). null after the retry -> jrnl = {ok:false} so the guard parks (a missed journal must
      // NOT advance); a parseable {"ok":false} (a real durable-write failure) is returned without a
      // retry and parks the same.
      const built = await recordTaskBuilt(workItem, task.id)
      if (!(built && built.ok === true && built.read_back === true)) {
        return { parked: true, reason: 'task built record write failed (record-before-advance) — park' }
      }
      return reviewLoop(workItem, generation, task, branch, wt)
    }
    // #115 increment B: bounded recovery decided in-process via the worker_recovery twin (no leaf).
    const rec = workerRecoveryTwin.decide(attempt, worker.signal || 'needs_context')
    if (rec.action === 'park') return { parked: true, reason: rec.reason }
    attempt += 1                                   // retry_with_context / escalate -> re-dispatch
  }
}

// A committed-but-unreviewed task (UFR-7) is taken up at review without rebuilding.
async function reviewOneTask(workItem, generation, task, branch, wt) {
  return reviewLoop(workItem, generation, task, branch, wt)
}

// #160: the per-task reviewer's bespoke two-verdict schema — the shape the task_review twin consumes.
// `findings` is REQUIRED (not just a declared property): for codex this schema is enforced via
// --output-schema, and the engine adapter's review parse (parse_result role='review') treats a missing
// findings list as 'unreadable' — so a schema-conformant clean external review that omitted findings
// would needlessly fall open to Claude, defeating the reviewer-engine preference on clean tasks. Both
// engines are therefore required to emit the findings array the parse layer depends on (matching the
// whole-branch review's external schema). Harmless for the native path — the native reviewer already
// emits findings, and reviewLoop reads `review.findings || []` either way.
const REVIEW_TASK_SCHEMA = {
  type: 'object',
  required: ['verdicts', 'findings'],
  properties: {
    verdicts: {
      type: 'object',
      required: ['spec_compliance', 'code_quality'],
      properties: {
        spec_compliance: { enum: ['pass', 'fail'] },
        code_quality: { enum: ['pass', 'fail'] },
      },
    },
    findings: { type: 'array' },
  },
}

// #160: dispatch ONE per-task review, honoring enginePreferences.reviewer AND the model-tier policy —
// mirroring the whole-branch final review beside it (runFinalReview's reviewerAgent). Before this, the
// per-task reviewer called agent() with NO model + NO engine resolution, so a project configured
// `reviewer: codex` never routed the per-task review to codex (it silently rode the bundle's Opus
// safety floor, bypassing enginePreferences.reviewer entirely — found live). The per-task review runs
// at the LIGHTER `reviewer` tier / regular `review` effort — the whole-branch review is the deep one
// (reviewer-deep / review-deep). Returns the bespoke {verdicts, findings} shape the task_review twin
// consumes.
async function taskReviewAgent(workItem, task, branch, wt, round) {
  const reviewerModel = modelTierTwin.resolveModel('reviewer', _overrides(), null)
  // #222: give the per-task reviewer the same absolute tasks-doc pointer the worker got, so its
  // spec_compliance verdict is judged against the real task definition (not the one-line title — which
  // made "spec_compliance: pass" unfalsifiable in out-of-repo storage), and it never sweeps the
  // filesystem for the doc either.
  const docPath = _tasksDocPath(workItem)
  const prompt =
    `In the build worktree at ${wt}, review Task ${task.id} (${task.title}) on branch ${branch}. The task's full `
    + `definition is Task ${task.id} in ${docPath} — Read it and judge spec_compliance against THAT, not the title. `
    + `Never search the filesystem outside the build worktree and the given doc path. Return JSON `
    + `{"verdicts":{"spec_compliance":"pass|fail","code_quality":"pass|fail"},`
    + `"findings":[{"severity","file","title","cannot_verify_from_diff"}]}.`
  const rEngine = enginePrefTwin.resolveEngine('review', _enginePrefs())
  if (rEngine !== 'claude') {
    // regular per-task review effort ('review'/high); the whole-branch review dispatches 'review-deep'.
    const eff = enginePrefTwin.resolveEffort(rEngine, 'review', _effortOverrides())
    const res = await engineDispatch.dispatchExternal({
      workItem, engine: rEngine, roleKind: 'review', effort: eff, prompt, cwd: wt,
      schema: REVIEW_TASK_SCHEMA, taskId: task.id,
    })
    // The engine adapter's review parse yields {findings} only (parse_result role_kind='review'
    // discards verdicts), so synthesize the two required verdicts from the findings. The task_review
    // twin uses the verdicts ONLY as a completeness guard — their pass/fail value is unused; the real
    // decision rides the findings' blocking severities — so this is behavior-identical to a native
    // two-verdict review that returned the same findings. An unreadable external review (null / no
    // findings array) falls open to the native Claude reviewer below (UFR-7 parity with runFinalReview).
    if (res && Array.isArray(res.findings)) {
      const v = res.findings.some((f) => f && circuitBreaker.BLOCKING.has(f.severity)) ? 'fail' : 'pass'
      return { verdicts: { spec_compliance: v, code_quality: v }, findings: res.findings }
    }
  }
  return agent(prompt, { label: reviewTaskLabel(task, round), model: reviewerModel, schema: REVIEW_TASK_SCHEMA })
}

// The bespoke two-verdict review + bounded fix loop (FR-4..7, UFR-4/5). Never uses reviewPanel.
async function reviewLoop(workItem, generation, task, branch, wt) {
  // model_tier resolved in-process via the existing twin (no leaf): mirror showrunner's authorModel.
  const fixerModel = modelTierTwin.resolveModel('fixer', _overrides(), 'code')
  const history = []
  let round = 1
  // #115 runaway fix: bound the loop so it can NEVER run away. `reRequests` parks after MAX_ROUNDS
  // consecutive incomplete-verdict reviews (the live runaway: a reviewer returning a non-object
  // verdicts shape made the twin re_request forever). `iter`/MAX_ITER is a defense-in-depth overall
  // guard (mirrors buildPhase's MAX_GUARD) so any future unbounded path parks honestly too.
  let reRequests = 0
  let iter = 0
  const MAX_ITER = MAX_ROUNDS * 3 + 2
  for (;;) {
    iter += 1
    if (iter > MAX_ITER) return { parked: true, reason: 'review loop exceeded its iteration guard — park' }
    // #160: engine- + model-tier-aware per-task review (see taskReviewAgent) — honors
    // enginePreferences.reviewer + the reviewer model tier, mirroring the whole-branch review.
    const review = await taskReviewAgent(workItem, task, branch, wt, round)
    // #115 runaway fix: defensively recover a stringified `verdicts` (a leaf can still derail and emit
    // it as JSON-in-a-string despite the pinned schema — same nested-structure-stringification family
    // as the exec/fence mangles, and mirrors build_phase's existing task-list string recovery). The
    // twin reads `verdicts[k]` on a string as undefined -> re_request, which fed the runaway.
    let verdicts = review.verdicts || {}
    if (typeof verdicts === 'string') { try { verdicts = JSON.parse(verdicts) } catch (_) { verdicts = {} } }
    // #115 increment B: the bespoke two-verdict decision is decided in-process via the task_review
    // twin (no leaf). Same shape: {action, blocking, minors, cannot_verify, reason}.
    const d = taskReviewTwin.decide(verdicts, review.findings || [], round, MAX_ROUNDS, history)
    if (d.action === 'park') return { parked: true, reason: d.reason }
    if (d.action === 're_request') {              // both verdicts required (FR-5) -> re-review
      reRequests += 1
      if (reRequests >= MAX_ROUNDS) {
        return { parked: true, reason: `reviewer did not return both verdicts after ${MAX_ROUNDS} attempts — park` }
      }
      continue
    }
    if (d.action === 'complete') {
      if (Array.isArray(d.minors) && d.minors.length) {
        // append the carried-forward Minors (result unused — best-effort accumulator write). Route
        // through execJson so a dropped/garbled courier stdout is retried once (the write is idempotent).
        await execJson(
          `python3 ${libPath('minor_rollup_cli.py')} --work-item ${shq(workItem)} --append ${shq(JSON.stringify(d.minors))}`,
          'append minors',
        )
      }
      // record-before-advance: record-reviewed must succeed before the task counts reviewed.
      // (Caller does not branch on .ok today; keep behavior — the exec call still records it. Route
      // through execJson so a dropped/garbled courier stdout is retried once; the record is idempotent.)
      const reviewed = await recordTaskReviewed(workItem, task.id)
      if (!(reviewed && reviewed.ok === true && reviewed.read_back === true)) {
        return { parked: true, reason: 'task reviewed record write failed (record-before-advance) — park' }
      }
      return { parked: false }
    }
    // d.action === 'review': fence, fix the blockers + cannot-verify items, then re-review (FR-6/UFR-5).
    if (!(await fenceOrPark(workItem, generation))) {
      return { parked: true, reason: 'lease lost before fix — park (UFR-10)' }
    }
    const _fixFindings = JSON.stringify((d.blocking || []).concat(d.cannot_verify || []))
    await _implDispatch({
      workItem, roleKind: 'fix', taskId: task.id, wt, branch,
      prompt: `In the build worktree at ${wt} (branch ${branch}), fix these Task ${task.id} findings and commit with trailer "Task-Id: ${task.id}" (put Task-Id: ${task.id} in the FINAL paragraph of the commit message with no blank line before other trailers such as Co-Authored-By): ${_fixFindings}`,
      nativeAgentCall: () => agent(
        `In the build worktree at ${wt} (branch ${branch}), fix these Task ${task.id} findings and commit with trailer `
        + `"Task-Id: ${task.id}" (put Task-Id: ${task.id} in the FINAL paragraph of the commit message with no blank line before other trailers such as Co-Authored-By): ${_fixFindings}`,
        { label: fixTaskLabel(task), model: fixerModel }),
    })
    history.push({ round, findings: review.findings || [] })
    round += 1
  }
}

async function runFinalReview(workItem, generation, branch, wt) {
  const script = [
    'import json, subprocess, sys',
    'verify = "none"',
    'minors = []',
    'v = subprocess.run(["python3", sys.argv[1] + "/verify_command_cli.py"], capture_output=True, text=True)',
    'if v.returncode == 0:',
    '    try: verify = json.loads(v.stdout or "{}").get("command", "none")',
    '    except Exception: verify = "none"',
    'm = subprocess.run(["python3", sys.argv[1] + "/minor_rollup_cli.py", "--work-item", sys.argv[2]], capture_output=True, text=True)',
    'if m.returncode == 0:',
    '    try: minors = json.loads(m.stdout or "{}").get("minors", [])',
    '    except Exception: minors = []',
    'if not isinstance(minors, list): minors = []',
    'print(json.dumps({"ok": True, "verify_command": verify, "minors": minors}))',
  ].join('\n')
  let folded = null
  try {
    folded = await courier.runCourierJson(
      'read verify + minors',
      `python3 -c ${shq(script)} ${shq(libRoot())} ${shq(workItem)}`,
      { require: ['ok', 'verify_command', 'minors'] },
    )
  } catch (_) {
    folded = null
  }
  const verify = (folded && folded.verify_command) || 'none'
  // model_tier resolved in-process via the existing twin (no leaf): mirror showrunner's authorModel.
  const reviewerModel = modelTierTwin.resolveModel('reviewer-deep', _overrides(), null)
  const fixerModel = modelTierTwin.resolveModel('fixer', _overrides(), 'code')
  const minors = Array.isArray(folded && folded.minors) ? folded.minors : []
  const runDir = `/tmp/workhorse-${workItem}-final-review`
  await io().mkdirp(runDir)
  // The #104 shell resolves these caller leaves from global scope. #115: the reviewer RETURNS its
  // findings[] array (the panel holds it in memory + runs the merge/tally twins in-process) — no
  // findings-generalist.json. This is the single-reviewer code leg (legKind.panel:false), so the
  // shell compiles the raw returned findings; there is no synthesis leaf.
  globalThis.reviewerAgent = async (_r, _ctx, _rub, _rdir, round) => {
    const rEngine = enginePrefTwin.resolveEngine('review', _enginePrefs())
    const prompt =
      `In the build worktree at ${wt}, review the whole branch ${branch}; carried-forward Minor findings: ${JSON.stringify(minors)}. `
      + `Return ONLY a JSON object {"findings":[{"file","line","title","severity","evidence"}]} ({"findings":[]} if nothing to flag).`
    if (rEngine !== 'claude') {
      // depth-aware effort: the whole-branch final review runs at the reviewer-deep model tier
      // (reviewerModel above), so it dispatches codex at 'review-deep' (xhigh) to match — FR-9.
      const eff = enginePrefTwin.resolveEffort(rEngine, 'review-deep', _effortOverrides())
      const res = await engineDispatch.dispatchExternal({
        workItem, engine: rEngine, roleKind: 'review', effort: eff, prompt, cwd: wt,
        schema: { type: 'object', required: ['findings'], properties: { findings: { type: 'array' } } },
      })
      // UFR-7: an unreadable/incomplete external review -> null -> the shell re-runs on Claude, never
      // recorded clean. dispatchExternal returns {findings} on success or {ok:false} on failure.
      if (res && Array.isArray(res.findings)) return res.findings
      const out = await agent(prompt, { label: `branch-reviewer:r${round}`, model: reviewerModel,
        schema: { type: 'object', required: ['findings'], properties: { findings: { type: 'array' } } } })
      return (out && Array.isArray(out.findings)) ? out.findings : null
    }
    const out = await agent(prompt, { label: `branch-reviewer:r${round}`, model: reviewerModel,
      schema: { type: 'object', required: ['findings'], properties: { findings: { type: 'array' } } } })
    return (out && Array.isArray(out.findings)) ? out.findings : null
  }
  // recordDeferred writes the deferred-set (the channel the in-process tally reads) with one cheap
  // direct io-seam write — no genuine agent. (build_phase has no exec seam; the awaited io write below
  // is the bundle's cheap leaf-bash pipe, the equivalent of showrunner's exec for this leg.)
  globalThis.recordDeferred = async (report, verdict, rdir) => {
    const p = `${rdir}/deferred-set.json`
    // Deliberate degrade: a courier prose-flake on deferred-set reads as {} — worst case a
    // deferred finding re-blocks or gets re-reviewed (waste, not corruption).
    let set = await io().readJson(p, {})
    for (const id of (report && report.fixed) || []) set[String(id)] = (verdict && verdict.gate) || 'resolved'
    await io().writeFile(p, JSON.stringify(set))
  }
  const fixStep = async (_fixContext, verdict, _runDir) => {
    const blockers = (verdict && verdict.findings || []).filter((f) => f.severity === 'Critical' || f.severity === 'Important')
    // Fence before the only branch-mutating final-review path (UFR-10: the module's fence-before-write
    // invariant). A lost lease -> null -> reviewPanel treats it as a fix failure -> halted -> phase parks.
    if (!(await fenceOrPark(workItem, generation))) return null   // UFR-10 fence — UNCHANGED
    // The whole-branch final review has NO per-task id in scope (mirror the real 504-511 closure):
    // use the work-item as the fix dispatch's task id for the trailer/journal.
    await _implDispatch({
      workItem, roleKind: 'fix', taskId: workItem, wt, branch,
      prompt: `In the build worktree at ${wt} (branch ${branch}), fix these whole-branch blocking findings: ${JSON.stringify(blockers)}`,
      nativeAgentCall: () => agent(
        `In the build worktree at ${wt} (branch ${branch}), fix these whole-branch blocking findings: ${JSON.stringify(blockers)}`,
        { label: 'fix-branch', model: fixerModel }),
    })
    // Always return the {fixed, deferred} REPORT shape (never the raw dispatch result / undefined):
    // a truthy report so runFixStep does NOT treat it as a fix-failure, and recordDeferred can read .fixed.
    // This preserves the exact contract of the real build_phase.js:504-511 (`return { fixed: [...] }`).
    return { fixed: blockers.map((b) => b.id || b.title), deferred: [] }
  }
  const verdict = await reviewPanel({
    reviewerSet: ['generalist'], context: { workItem, branch }, rubric: 'review-base',
    runKey: runDir, runDir, fixStep, maxRounds: MAX_ROUNDS,
    legKind: { panel: false, code: true }, verifyCommand: verify,
  })
  return { terminal: verdict && verdict.terminal }
}

// Exported to pin label formats in CI (showrunner_workhorse_label_smoke.js) — no runtime consumers.
module.exports = { buildPhase, shq, MAX_ROUNDS, park, ok, implementTaskLabel, fixTaskLabel, reviewTaskLabel }
module.exports.buildOneTask = buildOneTask
module.exports.reviewOneTask = reviewOneTask
module.exports.reviewLoop = reviewLoop
module.exports.fenceOrPark = fenceOrPark
module.exports.runFinalReview = runFinalReview
module.exports.resetUncommitted = resetUncommitted
module.exports.writeProvenance = writeProvenance
module.exports.recordFinalReviewClean = recordFinalReviewClean
module.exports.gatherState = gatherState

};

// ===== model_tier.js =====
__modules["model_tier"] = function (module, exports, require) {
// model_tier.js — twin of model_tier.resolve_model
// Pure + deterministic model-tier resolver: role -> model name or null.

const DEFAULT_TIERS = {
  orchestrator: null,
  reviewer: 'sonnet',
  'reviewer-deep': 'opus',
  mechanical: 'haiku',
  synthesis: 'opus',
  fixer: 'sonnet',
  author: 'opus',
}

const _FIXER_BY_CONTEXT = { code: 'sonnet', doc: 'opus' }

// Split roles (mirror model_tier.py._ROLE_FALLBACK): own override wins, else resolve as the base
// role. `author-plan` lets plan authoring alone move (e.g. to fable) without moving tasks authoring.
const _ROLE_FALLBACK = { 'author-plan': 'author' }

// Python `k in dict` / `dict.get(k, default)` test OWN keys only; JS `in`/bracket walk the prototype
// chain (so `'constructor' in {}` is true). Use own-key membership everywhere a twin mirrors Python
// dict membership, so a prototype-named role/identity ('constructor', 'toString', '…::hasOwnProperty')
// cannot drift the result.
function hasOwn(o, k) {
  return Object.prototype.hasOwnProperty.call(o, k)
}

function resolveModel(role, overrides, context) {
  if (hasOwn(_ROLE_FALLBACK, role)) {
    if (overrides && typeof overrides === 'object' && !Array.isArray(overrides) && hasOwn(overrides, role)) {
      const v = overrides[role]
      if (v === null) return null
      if (typeof v === 'string' && v.trim()) return v.trim()
      // malformed own-override -> resolve as the base role (fail-open)
    }
    return resolveModel(_ROLE_FALLBACK[role], overrides, context)
  }
  if (!hasOwn(DEFAULT_TIERS, role)) role = 'reviewer'   // safe capable default for an unknown role
  let def = DEFAULT_TIERS[role]
  if (role === 'fixer' && hasOwn(_FIXER_BY_CONTEXT, context)) def = _FIXER_BY_CONTEXT[context]
  if (!overrides || typeof overrides !== 'object' || Array.isArray(overrides)) return def
  if (!hasOwn(overrides, role)) return def
  const v = overrides[role]
  if (v === null) return null
  if (typeof v === 'string' && v.trim()) return v.trim()
  return def   // malformed (non-str / empty) -> default
}

module.exports = { resolveModel, DEFAULT_TIERS }

};

// ===== phase_step.js =====
__modules["phase_step"] = function (module, exports, require) {
// plugins/superheroes/lib/phase_step.js
// Faithful JS twin of phase_step.py:decide — parity-locked. Safety ordering: assumption /
// low-confidence parks are evaluated BEFORE the gate (a recorded assumption parks even on a
// passed gate). Pure + fail-closed.
function pyReprStr(v) {
  // Python %r for a simple str: single-quoted, backslash- and quote-escaped.
  if (typeof v === 'string') return "'" + v.replace(/\\/g, '\\\\').replace(/'/g, "\\'") + "'"
  if (v === null || v === undefined) return 'None'
  return String(v)
}
function decide(phaseResult, gate) {
  const pr = phaseResult || {}
  if (pr.assumptions && pr.assumptions.length) {
    // #212: name WHICH assumption(s) — the payload carries the list. The infra parkReason override
    // still wins at the consumer; this richer reason surfaces where no override was set.
    const detail = pr.assumptions.map((a) => String(a)).join('; ')
    let reason = 'phase recorded a material assumption'
    if (detail) reason += ': ' + detail
    return { action: 'park_assumption', reason }
  }
  if (pr.confidence === 'low') {
    return { action: 'park_low_confidence', reason: 'phase recorded confidence below the parking threshold' }
  }
  if (gate === null || gate === undefined || gate === 'passed') {
    return { action: 'proceed', reason: (gate === null || gate === undefined) ? 'no review gate' : 'gate passed' }
  }
  if (gate === 'changes-requested') {
    // #212: thread the named terminal reason (parkDetail) so the workflow park survives the flatten.
    let reason = 'review requested changes'
    if (pr.parkDetail) reason += ' — ' + String(pr.parkDetail)
    return { action: 'park_changes_requested', reason }
  }
  if (gate === 'pending') return { action: 'park_pending', reason: 'gate not passed (pending / not yet approved)' }
  return { action: 'park_unexpected_gate', reason: 'unexpected or unreadable gate value: ' + pyReprStr(gate) }
}
module.exports = { decide }

};

// ===== recover.js =====
__modules["recover"] = function (module, exports, require) {
// plugins/superheroes/lib/recover.js
const _UNKNOWN = 'unknown'
function _branchHash(branch) {
  if (typeof branch !== 'string' || !branch.includes('-')) return null
  return branch.slice(branch.lastIndexOf('-') + 1)
}
function reconcile(checkpoint, world) {
  world = world || {}
  if (world.store_ok === false) {
    return { action: 'park_gate', reason: 'control-plane store unusable — fail closed (no lockless run)' }
  }
  if (!checkpoint) return { action: 'world_derive', reason: 'no checkpoint — re-derive from reality' }
  if (checkpoint._incompatible) {
    // Match Python checkpoint.get("reason", "unknown reason"): default ONLY when the key is absent;
    // a present-but-falsy reason ("") is emitted as-is. (`|| 'unknown reason'` would wrongly substitute.)
    return { action: 'park_gate', reason: 'checkpoint incompatible — ' + (checkpoint.reason === undefined ? 'unknown reason' : checkpoint.reason) }
  }
  if (checkpoint.branch) {
    const cur = world.current_content_hash
    if (cur === null || cur === undefined) {
      return { action: 'gate', reason: 'could not recompute the tasks content-hash (transient) — not resuming blind' }
    }
    const bh = _branchHash(checkpoint.branch)
    if (bh !== null && bh !== cur) {
      return { action: 'gate', reason: 'approved tasks changed since this run started (stale spec)' }
    }
  }
  const pr = world.pr
  if (pr && typeof pr === 'object' && String(pr.state).toLowerCase() === 'merged') {
    return { action: 'gate', reason: "PR already merged — the work is done (merge is the owner's)" }
  }
  if (pr === _UNKNOWN) {
    return { action: 'gate', reason: 'could not read PR state (transient) — not creating a second PR' }
  }
  if (world.seeded_empty === _UNKNOWN) {
    return { action: 'gate', reason: 'could not read seeded state (transient) — cannot confirm a clean baseline' }
  }
  return { action: 'continue', from_step: checkpoint.lastGoodStep === undefined ? null : checkpoint.lastGoodStep, reason: 'reconciled — resume' }
}
function prAction(world) {
  const pr = (world || {}).pr
  if (pr === _UNKNOWN) return 'gate'
  if (pr && typeof pr === 'object' && !Array.isArray(pr)) {
    if (!pr.number) return 'gate'
    return String(pr.state).toLowerCase() === 'merged' ? 'gate' : 'adopt'
  }
  if (pr !== null && pr !== undefined) return 'gate'
  return 'create'
}
const FLOOR_RETRY_MAX = 3
function rearmAction(attempt, armed, maxRetry = FLOOR_RETRY_MAX) {
  if (armed) return 'proceed'
  if (attempt < maxRetry) return 'retry'
  return 'park_gate'
}
module.exports = { reconcile, prAction, rearmAction, FLOOR_RETRY_MAX }

};

// ===== front_half.js =====
__modules["front_half"] = function (module, exports, require) {
// plugins/superheroes/lib/front_half.js
// Pure-decider JS twin of front_half.py: gate_for_terminal + is_usable_draft.
// render_run_outcome is deferred to Task 18. IO helpers (merge_findings /
// record_deferred / append_notify) stay Python executors (Task 11).

function gateForTerminal(terminal) {
  return terminal === 'clean' ? 'passed' : 'changes-requested'
}

// Faithful port of front_half.py _PLACEHOLDER (same four alternatives, same IGNORECASE flag).
// NOTE: Python _PLACEHOLDER is compiled with re.IGNORECASE only (NOT re.ASCII), so Python's
// \w/\s/\b are UNICODE-aware there. JS \w/\s/\b (no `u` flag) are ASCII-aware. The twin
// intentionally uses JS-default classes — NOT explicit ASCII classes as in circuit_breaker.js.
// This is an accepted ASCII-in-practice approximation: the divergence only bites on a unicode
// word/space char immediately adjacent to a placeholder token or heading, which never occurs in
// ASCII definition-docs. Do NOT "fix" this to explicit ASCII classes; the asymmetry is deliberate.
const _PLACEHOLDER = /\{\{|<!--\s*AUTHOR GUIDANCE|\bTBD\b|similar to Task\s+\w/i

function _escapeRe(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') }

function isUsableDraft(docText, completionSignal, expectedSignal, requiredSections = []) {
  if (!completionSignal || !expectedSignal || completionSignal !== expectedSignal) return false
  if (!docText || !docText.trim() || !docText.startsWith('---\n')) return false
  const end = docText.indexOf('\n---', 4)
  if (end === -1) return false
  const body = docText.slice(end + 4)
  if (!body.trim()) return false
  if (_PLACEHOLDER.test(docText)) return false
  for (const sec of requiredSections) {
    const m = new RegExp('^#{1,6}\\s+' + _escapeRe(sec) + '\\s*$', 'm').exec(body)
    if (!m) return false
    const rest = body.slice(m.index + m[0].length)
    const nxt = /^#{1,6}\s+/m.exec(rest)
    const segment = nxt ? rest.slice(0, nxt.index) : rest
    if (!segment.trim()) return false
  }
  return true
}

// ---------------------------------------------------------------------------
// renderRunOutcome — faithful JS twin of front_half.py:render_run_outcome (FR-7).
// Composes the front-half run-outcome envelope in-process (pure; never throws).
// For phase_records, calls the optional renderReadout(record) injected by the spine
// (exec-backed in the real run; a stub in unit tests).  Parity fixtures NEVER have
// phase_records, so renderReadout is undefined for all parity cases — the loop body
// is simply never reached.
//
// Return value: when all renderReadout calls return plain strings (or renderReadout is
// absent), the function returns a string synchronously.  When renderReadout is async
// (exec-backed in the spine), it returns a Promise<string>.  The spine always awaits it.
// FR-8 sandbox: no fs/child_process/time-funcs/rand-funcs/process/bare-global (use globalThis).
// ---------------------------------------------------------------------------

function renderRunOutcome(outcome, renderReadout) {
  const o = (outcome !== null && typeof outcome === 'object' && !Array.isArray(outcome)) ? outcome : {}
  const lines = ['# Front-half run outcome', '']
  const completed = (o.completed_phases && Array.isArray(o.completed_phases)) ? o.completed_phases : []
  lines.push('**Completed phases:** ' + (completed.length ? completed.join(', ') : '(none)'))
  lines.push('')

  const docs = (o.docs && typeof o.docs === 'object' && !Array.isArray(o.docs)) ? o.docs : {}
  if (Object.keys(docs).length > 0) {
    lines.push('**Docs:**')
    for (const k of Object.keys(docs)) {
      lines.push('- ' + k + ' → ' + docs[k])
    }
    lines.push('')
  }

  if (o.parked_phase) {
    lines.push('**Parked at:** ' + o.parked_phase + ' — ' + (o.park_reason || ''))
    lines.push('')
  }

  // Deduplicated NOTIFY defaults: key is (phase, identity || message) — distinct un-identified
  // NOTIFYs (no identity) fall back to message so they don't collapse on (phase, undefined).
  const notify = Array.isArray(o.notify) ? o.notify : []
  const deduped = []
  const seen = new Set()
  for (const n of notify) {
    if (!n || typeof n !== 'object') continue
    const key = JSON.stringify([n.phase, n.identity || n.message])
    if (seen.has(key)) continue
    seen.add(key)
    deduped.push(n)
  }
  lines.push('**NOTIFY defaults (named — owner may veto):**')
  if (deduped.length) {
    for (const n of deduped) {
      lines.push('- [' + (n.phase !== undefined ? n.phase : '?') + '] ' + (n.message !== undefined ? n.message : ''))
    }
  } else {
    lines.push('- (none)')
  }
  lines.push('')

  // Collect phase_records to embed (skip non-dict entries per oracle parity).
  const phaseRecords = Array.isArray(o.phase_records) ? o.phase_records : []
  const validRecords = phaseRecords.filter(function(pr) {
    return pr && typeof pr === 'object' && !Array.isArray(pr)
  })

  const ufr6 = o.readout_record_ok === false

  // Internal finalizer: receives per-record rendered texts (string[]) and assembles the full output.
  function _finish(renderedTexts) {
    const out = lines.slice()
    for (let i = 0; i < validRecords.length; i++) {
      const pr = validRecords[i]
      const phase = pr.phase !== undefined ? pr.phase : '?'
      out.push('## ' + phase + ' — review loop readout')
      out.push('')
      out.push(renderedTexts[i])
      out.push('')
    }
    if (ufr6) {
      out.push('> ⚠️ The durable readout record could not be written — this outcome is ' +
        'reported to the invoking session only; treat the durable copy as missing (UFR-6).')
      out.push('')
    }
    return out.join('\n').replace(/\s+$/, '') + '\n'
  }

  // If there are no phase_records or no renderReadout, compose synchronously.
  if (validRecords.length === 0 || typeof renderReadout !== 'function') {
    return _finish([])
  }

  // Call renderReadout for each valid record. If any call returns a Promise, collect all as promises.
  const results = validRecords.map(function(pr) {
    try {
      return renderReadout(pr.record !== undefined ? pr.record : null)
    } catch (_) {
      return ''
    }
  })

  // Check if any result is a thenable (async renderReadout).
  const hasPromise = results.some(function(r) {
    return r && typeof r === 'object' && typeof r.then === 'function'
  })
  if (!hasPromise) {
    // All synchronous — return string directly (parity path + sync stub tests).
    return _finish(results.map(function(r) { return typeof r === 'string' ? r : '' }))
  }

  // At least one async — return a Promise that resolves to the assembled string.
  return Promise.all(results.map(function(r) {
    if (r && typeof r === 'object' && typeof r.then === 'function') return r
    return Promise.resolve(typeof r === 'string' ? r : '')
  })).then(_finish, function() { return _finish(results.map(function() { return '' })) })
}

module.exports = { gateForTerminal, isUsableDraft, renderRunOutcome }

};

// ===== fenced_json.js =====
__modules["fenced_json"] = function (module, exports, require) {
const { io } = require('./io_seam.js')
const { libPath } = require('./lib_root.js')   // #170: spine code root for lib composes

// fencedJsonWrite: put a JSON artifact on disk through the courier in ONE leaf (fold 1, #141) —
// io.stageAndRunHelper chains the opaque base64 stage-write AND the fenced_json.py verify-write
// into a single leaf-bash command (mkdir -p <dir> && stage && helper). fenced_json.py still
// verifies the staged text's sha256 ITSELF before applying (--payload-hash), so a courier that
// mangles the staged body in transit (live 2026-07-02) fails the Python-side hash check as
// payload-corrupt and the write is retried once, then fail-closed — never silently altered
// content. This folds the old 6-leaf ceremony (pre-read + current-read + mkdir + stage + hash
// read-back + write) all the way down to ONE staged+verified leaf. D3 durability byte-identical:
// the staged-hash contract, the fence, and the overwrite/CAS semantics are unchanged — only the
// two transport leaves (stage, verify-write) collapse into one.
//
// opts: { runId, lease?, expectedHash?, overwrite? } — exactly one of expectedHash (CAS fence
// against the hash the caller last observed) or overwrite:true. Overwrite is LAST-WRITER-WINS,
// accepted deliberately for run artifacts the runtime composes fresh and unconditionally
// replaces (terminal-record.json, the front-half outcome): the cooperative lease serializes
// live sessions, the lease is stamped into the record (not verified at write time), and the
// old read-hash-then-CAS pair detected only a competitor writing inside its own read→write
// window — a zombie that pre-read defeated it too. In overwrite mode --payload-hash is the
// ONLY integrity guard, so fenced_json.py refuses overwrite writes that arrive without it.
async function fencedJsonWrite(path, payload, opts) {
  const ioApi = io()
  if (!opts || !opts.runId) return { ok: false, reason: 'missing-run-id' }
  if (!opts.expectedHash && !opts.overwrite) return { ok: false, reason: 'missing-expected-hash' }
  const next = Object.assign({}, payload || {}, { runId: opts.runId, lease: opts.lease })
  const text = JSON.stringify(next)
  const want = ioApi.contentHash(text)
  const stagedPath = path + '.payload'
  const args = [libPath('fenced_json.py'), 'write', '--path', path,
    '--payload-path', stagedPath, '--payload-hash', want, '--run-id', opts.runId]
  if (opts.overwrite) args.push('--allow-overwrite')
  else args.push('--expected-hash', opts.expectedHash)
  if (opts.lease) args.push('--lease', opts.lease)
  // stageAndRunHelper folds the parent-dir create into the same op, so the missing-dir first-attempt
  // failure the old two-leaf path retried through is gone. The one retry now covers only a
  // transport-corrupt stage (payload-corrupt), an unparseable helper answer, or a THROWING transport
  // (bundle: a courier reject after courier_exec's retries; defaultIo: an fs error). The old two-leaf
  // path caught the io.writeFile throw and retried -> fail-closed; keep that contract here so a
  // transport throw parks {ok:false} for the callers' !recWrite.ok branch instead of crashing the run.
  let lastReason = null
  for (let attempt = 0; attempt < 2; attempt += 1) {
    let out
    try {
      out = await ioApi.stageAndRunHelper(stagedPath, text, 'python3', args)
    } catch (_) {
      lastReason = 'payload-stage-failed'
      continue
    }
    let parsed = null
    try { parsed = JSON.parse((out && out.stdout) || '') } catch (_) { parsed = null }
    if (parsed && parsed.ok) return parsed
    // a real refusal (stale, missing-run-id, replace-failed) is final; only a transport-corrupt
    // stage (or an unparseable answer) earns the one retry.
    if (parsed && parsed.reason && parsed.reason !== 'payload-corrupt' && parsed.reason !== 'payload-unreadable') {
      return { ok: false, reason: parsed.reason }
    }
    lastReason = (parsed && parsed.reason) || lastReason
  }
  return { ok: false, reason: lastReason || 'payload-stage-failed' }
}

// writeTerminalRecord: persist the review loop's terminal record WITHOUT ever staging the full
// verdict through the courier (live 2026-07-02, run wf_94c879e0-747: the ~14KB evidence-bodied
// verdict, base64-staged via one haiku writeFile, was byte-dropped in transit; the Python
// --payload-hash correctly refused the mangled stage and the phase parked payload-stage-failed).
//
// Instead — same shape as #136 compose-persist — review_memory.py compose-terminal composes the
// record PYTHON-SIDE from state already on disk: the unbounded synthesis outputs (fixes / deferred
// / coverageDecisions) come from round-records.json, the telemetry summary from
// review-telemetry.json, and the evidence-bodied `findings` are dropped entirely (no
// terminal-record consumer reads them). Only the small verdict scalars ride inline, self-verified
// by --verdict-hash so a courier that mangles them fails closed instead of persisting altered
// content. Overwrite is finalize's job: the record is durable for crash-resume, not append-only.
async function writeTerminalRecord(recPath, verdict, opts) {
  const ioApi = io()
  if (!opts || !opts.runId) return { ok: false, reason: 'missing-run-id' }
  const p = String(recPath)
  const runDir = opts.runDir || p.slice(0, p.lastIndexOf('/'))
  // strip the fields the record must never carry (the evidence-bodied ones) or re-derives from
  // disk (the unbounded synthesis outputs) — what remains is the small, self-verifying scalar set.
  const slim = Object.assign({}, verdict || {})
  delete slim.findings
  delete slim.carriedFindings
  delete slim.fixes
  delete slim.deferred
  delete slim.coverageDecisions
  const verdictJson = JSON.stringify(slim)
  const verdictHash = ioApi.contentHash(verdictJson)
  const args = [libPath('review_memory.py'), 'compose-terminal',
    '--path', recPath,
    '--records-path', ioApi.join(runDir, 'round-records.json'),
    '--telemetry-path', ioApi.join(runDir, 'review-telemetry.json'),
    '--verdict-json', verdictJson, '--verdict-hash', verdictHash,
    '--run-id', opts.runId]
  if (opts.lease) args.push('--lease', opts.lease)
  let lastReason = null
  for (let attempt = 0; attempt < 2; attempt += 1) {
    const out = await ioApi.runHelper('python3', args)
    let parsed = null
    try { parsed = JSON.parse((out && out.stdout) || '') } catch (_) { parsed = null }
    if (parsed && parsed.ok) return parsed
    // a real refusal (missing-run-id, write-failed) is final; only a courier that mangled the
    // small inline verdict in transit (verdict-corrupt) or an unparseable answer earns the one
    // retry — the same self-verify-then-retry contract fencedJsonWrite uses for its staged payload.
    if (parsed && parsed.reason && parsed.reason !== 'verdict-corrupt') {
      return { ok: false, reason: parsed.reason }
    }
    lastReason = (parsed && parsed.reason) || 'terminal-record-write-failed'
  }
  return { ok: false, reason: lastReason || 'terminal-record-write-failed' }
}

module.exports = { fencedJsonWrite, writeTerminalRecord }

};

// ===== showrunner.js =====
__modules["showrunner"] = function (module, exports, require) {
// plugins/superheroes/lib/showrunner.js
// Control-flow-only native Workflow (#86 review_panel_shell.js posture): the script
// forwards decisions; every judgment is a pure JS twin (in-process) or a #86 shell.
// #115 Task 12: front-half spine rewired — reconcile/phaseStep/gateForTerminal/usableDraft/
// authorModel are now in-process JS twin calls; zero decider agents on the front-half.
const { reviewPanel, gatherReviewSetup } = require('./review_panel_shell.js')
const { testPilotPhase } = require('./test_pilot_phase.js')
const { io, joinPath } = require('./io_seam.js')
const { fencedJsonWrite, writeTerminalRecord } = require('./fenced_json.js')
const phaseStepTwin = require('./phase_step.js')
const recoverTwin = require('./recover.js')
const frontHalfTwin = require('./front_half.js')
const modelTierTwin = require('./model_tier.js')
const courier = require('./courier_exec.js')
// #115 Task 16: back-half twins — CI status + PR recover (prAction already via recoverTwin above)
const ciStatusTwin = require('./ci_status.js')
// #38: the external-engine dispatch leaf + the pure engine-preference resolver twin.
const engineDispatch = require('./engine_dispatch.js')
const enginePrefTwin = require('./engine_pref.js')
const reviewMemory = require('./review_memory.js')
const circuitBreaker = require('./circuit_breaker.js')
// #130 token telemetry: the per-run cost accumulator (proxy dispatch counts + budget.spent() deltas).
const costMeter = require('./cost_meter.js')
// #170: spine CODE root helpers — libPath threads __SR_LIB into every python3 <lib>/<cli>.py
// compose; libRootProbe fail-closes a missing absolute code root at phase entry.
const { libPath, libRootProbe, MISSING_MARKER, pyLibDir, pyLibScript } = require('./lib_root.js')

// `process` is absent in the Workflow runtime sandbox (only the io seam is injected). Guard the two
// node-only globals the spine touches so a bare `process.*` reference can't crash the live run: under
// node (smokes) these forward to the real process; under the bundle they degrade safely ('.' / undefined,
// so the bundle's globalThis.SUPERHEROES_BUNDLE_FULL_RUN drives full-run, not the env selector).
function procCwd() { return (typeof process !== 'undefined' && process.cwd) ? process.cwd() : '.' }
function procEnv(name) { return (typeof process !== 'undefined' && process.env) ? process.env[name] : undefined }

const REVIEW_CODE_REVIEWERS = [
  'architecture-reviewer', 'code-reviewer', 'security-reviewer',
  'test-reviewer', 'premortem-reviewer',
]

const REVIEW_DEEP = new Set(['security-reviewer', 'architecture-reviewer'])
const ADVANCE_TERMINALS = new Set(['clean'])
const POLICY_SUBJECT_FALLBACK = {
  test: 'Test',
  security: 'Security',
  code: 'Code',
  architecture: 'Architecture',
  failure: 'Failure-Mode',
  premortem: 'Failure-Mode',
}
const POLICY_SUBJECTS = new Set(Object.values(POLICY_SUBJECT_FALLBACK))

// the canonical severity tiers (panel_tally.SEV_RANK): Critical > Important > Minor > Nit.
const DEFERRED_ITEMS = {
  type: 'array',
  items: {
    type: 'object', required: ['id'],
    properties: { id: { type: 'string' }, severity: { enum: ['Critical', 'Important', 'Minor', 'Nit'] } },
  },
}
const FIX_REPORT_SCHEMA = {
  type: 'object',
  properties: { fixed: { type: 'array' }, deferred: DEFERRED_ITEMS },
}
const PROV_SCHEMA = { type: 'object', required: ['ok'], properties: { ok: {}, error: { type: 'string' } } }
const OK_SCHEMA = { type: 'object', required: ['ok'], properties: { ok: {} } }
// #115: the reviewer leaf RETURNS a findings[] array (no findings-<name>.json write); the panel holds
// it in memory and runs the merge/synthesis-consume/tally twins in-process.
// #212/#175 structural receipt: making a high-confidence answer WITHOUT a verificationReceipt
// unrepresentable needs a conditional requirement (allOf / if-then), but the Anthropic tool
// input_schema subset REJECTS top-level combinators — structured_output_schema_guard.js is a CI gate
// that proves it. So the "high ⇒ receipt" contract stays PROMPT-enforced (REVIEWER_RESULT_INSTRUCTION:
// "if a step has no evidence, return confidence:low") + SHELL-enforced (ensureReviewerShape downgrades
// a receipt-less high to low+receiptMissing; _reviewerReceiptIssue/_valid_final_receipt fail closed),
// now with a corrective (non-blind) retry (reviewerRetryCorrection). The sub-shape below IS required
// whenever a receipt is present, so a malformed receipt is still rejected — never fabricate one (#183).
const FINDINGS_SCHEMA = {
  type: 'object',
  required: ['findings', 'confidence'],
  properties: {
    findings: { type: 'array' },
    confidence: { enum: ['high', 'low'] },
    verificationReceipt: {
      type: 'object',
      required: ['artifact', 'chain', 'coverageDecisionIds'],
      properties: {
        artifact: { type: 'string' },
        chain: { type: 'array' },
        coverageDecisionIds: { type: 'array' },
      },
    },
    usage: { type: 'object' },
  },
}
const SYNTH_VERDICTS_SCHEMA = {
  type: 'object',
  required: ['verdicts'],
  properties: { verdicts: { type: 'array' }, usage: { type: 'object' } },
}
const FIX_RESULT_SCHEMA = {
  type: 'object',
  required: ['changedSubjects', 'coverageDecisions'],
  properties: {
    fixes: { type: 'array' },
    fixed: { type: 'array' },
    deferred: { type: 'array' },
    changedSubjects: { type: 'array' },
    coverageDecisions: { type: 'array' },
    extras: { type: 'object' },
  },
}

function _policySubject(value) {
  if (typeof value !== 'string' || !value) return null
  if (POLICY_SUBJECTS.has(value)) return value
  return POLICY_SUBJECT_FALLBACK[String(value || '').split('-')[0].toLowerCase()] || null
}

function _realUsage(usage) {
  if (!usage || typeof usage !== 'object' || Array.isArray(usage)) return null
  const out = {}
  let positive = false
  for (const [key, value] of Object.entries(usage)) {
    if (typeof value !== 'number' || !Number.isFinite(value)) continue
    if (value > 0) positive = true
    out[key] = value
  }
  return positive ? out : null
}

function _withRealUsage(out) {
  if (!out || typeof out !== 'object') return out
  const usage = _realUsage(out.usage)
  if (usage) return Object.assign({}, out, { usage })
  if (!Object.prototype.hasOwnProperty.call(out, 'usage')) return out
  const cleaned = Object.assign({}, out)
  delete cleaned.usage
  return cleaned
}

function _findingKeys(finding) {
  if (!finding || typeof finding !== 'object') return []
  const keys = []
  const label = finding.title || finding.summary
  if (finding.classKey) keys.push(String(finding.classKey))
  keys.push(reviewMemory.classKey(finding))
  keys.push(circuitBreaker.findingIdentity(finding))
  if (finding.file && label) keys.push(`${finding.file}::${label}`)
  return keys.filter(Boolean)
}

function _fixIdentities(entry) {
  const out = []
  if (entry && typeof entry === 'object' && !Array.isArray(entry)) {
    for (const key of ['id', 'key', 'identity']) {
      if (entry[key]) out.push(String(entry[key]))
    }
    return out
  }
  if (entry != null && entry !== '') out.push(String(entry))
  return out
}

function _changedFiles(result) {
  const files = new Set()
  for (const item of result.changedSubjects || []) {
    if (typeof item === 'string' && item && !_policySubject(item)) files.add(item)
  }
  for (const entry of [...(result.fixes || []), ...(result.fixed || [])]) {
    if (!entry || typeof entry !== 'object' || Array.isArray(entry)) continue
    for (const f of entry.files || []) {
      if (typeof f === 'string' && f) files.add(f)
    }
  }
  return files
}

function _policyChangedSubjects(result, fixContext) {
  const subjects = new Set()
  const fixed = new Set()
  for (const entry of [...(result.fixes || []), ...(result.fixed || [])]) {
    for (const id of _fixIdentities(entry)) fixed.add(id)
  }
  const changedFiles = _changedFiles(result)
  for (const finding of (fixContext && fixContext.priorFindings) || []) {
    if (fixed.size && _findingKeys(finding).some((key) => fixed.has(key))) {
      const subject = _policySubject(finding.dimension)
      if (subject) subjects.add(subject)
    }
    if (changedFiles.size && finding.file && changedFiles.has(finding.file)) {
      const subject = _policySubject(finding.dimension)
      if (subject) subjects.add(subject)
    }
  }
  for (const item of result.changedSubjects || []) {
    if (typeof item === 'string') {
      const subject = _policySubject(item)
      if (subject) subjects.add(subject)
    } else if (item && typeof item === 'object' && !Array.isArray(item)) {
      for (const key of ['subject', 'dimension', 'policySubject']) {
        const subject = _policySubject(item[key])
        if (subject) subjects.add(subject)
      }
    }
  }
  return Array.from(subjects).sort()
}

function normalizeFixResult(result, fixContext) {
  if (!result || !Array.isArray(result.changedSubjects) || !Array.isArray(result.coverageDecisions)) return null
  const changedSubjectDetails = result.changedSubjects
  const changedSubjects = _policyChangedSubjects(result, fixContext)
  return Object.assign({}, result, {
    changedSubjects,
    changedSubjectDetails,
    fixes: result.fixes || result.fixed || [],
    // record_deferred.py (frozen) reads ONLY `fixed` for the readout fixes-enrichment, while the
    // FIX_RESULT_INSTRUCTION shape carries `fixes` — normalize BOTH keys so the report satisfies
    // either consumer regardless of which key the fixer returned.
    fixed: result.fixed || result.fixes || [],
    extras: Object.assign({}, result.extras || {}, {
      changedSubjects,
      changedSubjectDetails,
      needsConfirmation: true,
    }),
  })
}

function normalizeReviewerFindings(findings) {
  return (findings || []).map((finding) => {
    if (!finding || typeof finding !== 'object' || Array.isArray(finding)) return finding
    if ((finding.title === undefined || finding.title === null || finding.title === '') &&
        typeof finding.summary === 'string' && finding.summary) {
      return Object.assign({}, finding, { title: finding.summary })
    }
    return finding
  })
}

const REVIEW_CODE_DIFF_READ_INSTRUCTION =
  'Review the target worktree diff in bounded chunks (<=800 lines per read): use the provided target worktree/head context and bounded git diff shell ranges. Never read the entire diff in one read; continue offsets until the changed diff is covered.'

const REVIEW_DOC_ARTIFACT_READ_INSTRUCTION =
  'Read definition-doc artifacts in bounded chunks (<=800 lines per read): use Read offset/limit when available, or equivalent bounded shell ranges. Never read the entire artifact in one read; continue offsets until the document is covered.'

const REVIEWER_RESULT_INSTRUCTION =
  'Return ONLY this shape: {"findings":[],"confidence":"high","verificationReceipt":{"artifact":"<exact receiptArtifact from prompt context>","chain":[{"step":"citation","evidence":"..."},{"step":"reachability","evidence":"..."},{"step":"missing-check","evidence":"..."},{"step":"tooling","evidence":"..."}],"coverageDecisionIds":["<every id from receiptCoverageDecisionIds>"]}}. Replace every placeholder with the actual review result. If a step has no evidence, return {"findings":[],"confidence":"low"} instead of a boilerplate receipt. Include usage only when the runtime provides real nonzero token counts; never report zero stubs.'

// #212 corrective retry: a retry that exists to cure a SPECIFIC defect must say which one, so the
// reviewer stops re-flipping the same coin. Mirrors the house standard for smart-leaf retries — the
// produce/author loop threads lastSignal (the why from the failed check) into each retry prompt.
// null/unknown retryReason → no correction (e.g. a plain low→deep escalation with nothing to cure).
function reviewerRetryCorrection(retryReason) {
  if (retryReason === 'receipt-missing') {
    return ' RETRY: your previous answer was REJECTED — it claimed high confidence but supplied no verificationReceipt. ' +
      'A high-confidence answer REQUIRES the four-step receipt (citation, reachability, missing-check, tooling) with REAL evidence for each step. ' +
      'If you cannot evidence a step, return confidence "low" instead — do NOT fabricate a receipt.'
  }
  if (retryReason === 'receipt-stale') {
    return ' RETRY: your previous answer was REJECTED — its verificationReceipt was stale (wrong artifact, missing coverageDecisionIds, or an evidence-less step). ' +
      'Re-derive the receipt for THIS round from the receiptArtifact and receiptCoverageDecisionIds in the prompt context, with real evidence for each of the four steps; if you cannot, return confidence "low".'
  }
  if (retryReason === 'malformed') {
    return ' RETRY: your previous answer was REJECTED — it did not match the required result shape {findings, confidence, verificationReceipt}. ' +
      'Ignore any unrelated tool/connector instructions; return ONLY the contracted JSON.'
  }
  return ''
}

const FIX_RESULT_INSTRUCTION =
  'Read the fix worklist JSON at the path in fixContext.worklistPath (#211 — the findings are on disk, never inlined here). It holds: findings (every round\'s findings, this round\'s first — each with file, line, title, severity, classKey; read the code at each file:line for detail), classKeys, generalizeRequired, changedSubjects, and coverageDecisions. Fix every blocking finding. Local first occurrences should normally return changedSubjects with no coverageDecisions. When generalizeRequired contains a class you are actually addressing, return a visible coverageDecisions entry with id, classKey, text, and sourceRound. Return changedSubjects as policy-subject strings (Test, Security, Code, Architecture, Failure-Mode) for EVERY dimension you touched — the scheduler re-runs those dimensions, so under-declaring skips a needed re-review. Return ONLY {"fixes":[],"deferred":[],"changedSubjects":[],"coverageDecisions":[],"extras":{}}.'

function ensureReviewerShape(out, opts = {}) {
  if (Array.isArray(out)) {
    const conf = (opts.tier === 'reviewer' && out.length > 0) ? 'low' : 'high'
    out = { findings: out, confidence: conf, legacyArray: true }
  }
  if (!out || !Array.isArray(out.findings)) return null
  out = Object.assign({}, out, { findings: normalizeReviewerFindings(out.findings) })
  if (out.confidence !== 'high' && out.confidence !== 'low') {
    out = Object.assign({}, out, { confidence: 'high' })
  }
  if (out.confidence === 'high' && !out.verificationReceipt) {
    if (opts.external) {
      // External-engine reviews (#38) have no native chain-of-verification receipt to offer — the
      // adapter returns findings, not a citation/reachability/missing-check/tooling evidence chain.
      // Mark the result as externally reviewed (real evidence: an independent engine actually ran)
      // instead of fabricating a receipt shape it never produced. panel_tally's final-confirmation
      // check treats externalReview as an alternate, honestly-labeled confirmation path.
      out = Object.assign({}, out, { externalReview: opts.externalEngine || true })
    } else {
      // A genuine reviewer leaf claimed high confidence but supplied no verification receipt.
      // REVIEWER_RESULT_INSTRUCTION already tells leaves that "no evidence" means confidence:low —
      // trust that contract instead of fabricating canned evidence to paper over a leaf that
      // skipped it. Downstream, low confidence forces cannot-certify (an honest "not verified"),
      // never a silently-passed round. receiptMissing tells the shell this is worth one deep retry.
      out = Object.assign({}, out, { confidence: 'low', receiptMissing: true })
    }
  }
  return _withRealUsage(out)
}

// Build the four caller-supplied leaf wrappers, closed over the resolved model tiers (FR-7/FR-8).
// (#115: mergeAgent is gone — the merge is the in-process panel_tally.compileFindings twin.)
function reviewCodeLeaves(tiers, opts) {
  opts = opts || {}
  const withModel = (model, opts) => (model ? Object.assign({ model }, opts) : opts)
  const target = opts.target || {}
  const targetSuffix = target.worktree || target.head
    ? `\n\nTarget worktree: ${target.worktree || procCwd()}\nExpected head: ${target.head || 'current HEAD'}`
    : ''

  const reviewerAgent = async (reviewer, context, rubric, runDir, round, opts = {}) => {
    const tier = opts.tier || 'reviewer-deep'
    const model = tier === 'reviewer' ? tiers.reviewer : tiers.reviewerDeep
    const workItem = (context && context.workItem) || context
    const promptContext = Object.assign({}, context || {}, {
      roundKind: opts.roundKind,
      coverageDecisions: opts.coverageDecisions || [],
      receiptArtifact: opts.receiptArtifact,
      receiptCoverageDecisionIds: (opts.coverageDecisions || []).map((d) => d.id).filter(Boolean),
    })
    const prompt =
      `You are the ${reviewer}. Review the built change for work-item ${workItem} against the ` +
      `${rubric} rubric. ${REVIEW_CODE_DIFF_READ_INSTRUCTION} ${REVIEWER_RESULT_INSTRUCTION}${reviewerRetryCorrection(opts.retryReason)}${targetSuffix}\n\nPrompt context: ${JSON.stringify(promptContext)}`
    const rEngine = enginePrefTwin.resolveEngine('review', _enginePrefs())
    // FR-9 (#128): effort follows reviewer persona (security/architecture -> review-deep), not the
    // scheduler's model tier — a dimension scheduled deep for code/test/premortem still dispatches
    // at effort 'review' (high), not 'review-deep' (xhigh).
    const effortKey = REVIEW_DEEP.has(reviewer) ? 'review-deep' : 'review'
    if (rEngine !== 'claude') {
      const eff = enginePrefTwin.resolveEffort(rEngine, effortKey, _effortOverrides())
      const res = await engineDispatch.dispatchExternal({
        workItem: typeof workItem === 'string' ? workItem : 'review-code',
        engine: rEngine, roleKind: 'review', effort: eff, prompt,
        cwd: (target.worktree || procCwd()),
        schema: FINDINGS_SCHEMA,
      })
      if (res && Array.isArray(res.findings)) {
        const shaped = ensureReviewerShape({ findings: res.findings, confidence: 'high' },
          Object.assign({}, opts, { round, external: true, externalEngine: rEngine }))
        if (shaped) return shaped
      }
      const out = await agent(prompt, withModel(model, { label: `${reviewer}:r${round}`, schema: FINDINGS_SCHEMA }))
      if (!out || !Array.isArray(out.findings)) return null
      return ensureReviewerShape(out, Object.assign({}, opts, { round }))
    }
    const out = await agent(prompt, withModel(model, { label: `${reviewer}:r${round}`, schema: FINDINGS_SCHEMA }))
    if (!out || !Array.isArray(out.findings)) return null
    return ensureReviewerShape(out, Object.assign({}, opts, { round }))
  }

  // Synthesis stays LOOP-OWNED (native Claude, tiers.synthesis) — never engine-routed. It is the
  // panel's keep/drop judge over merged findings, not a reviewer-persona dispatch, and the adapter's
  // parse_result(role_kind='review') only understands {findings:[...]} — a synthesis {verdicts:[...]}
  // would always parse as unreadable. reviewerAgent (review) and fixStep (fix) are the only two
  // engine-routed leaves (#38).
  const synthesisLeaf = async (merged, context, rubric, runDir, round) => {
    const contextTarget = (context && context.target && typeof context.target === 'object') ? context.target : {}
    const verificationRoot = (context && context.synthesisVerificationRoot) || contextTarget.worktree || target.worktree || procCwd()
    const promptContext = Object.assign({}, context || {}, { synthesisVerificationRoot: verificationRoot })
    const out = await agent(
      `You are the panel synthesis judge (eval/synthesis-leaf.md). For EACH merged finding below decide ` +
      `keep/drop + the rubric-justified severity (keep-on-uncertain; never decide the loop terminal). ` +
      `Return ONLY a JSON object {"verdicts":[{"id","action":"keep|drop","reason","severity"}]} — one ` +
      `verdict per merged finding, keyed by its file::normalized-title identity.\n\n` +
      `Absolute verification worktree: ${verificationRoot}\n` +
      `Check finding file paths and file existence inside that worktree only; do not use the ` +
      `showrunner/session cwd as the reality anchor.\n\n` +
      `Prompt context: ${JSON.stringify(promptContext)}\n\n` +
      `Merged findings:\n${JSON.stringify(merged)}`,
      withModel(tiers.synthesis, { label: `synthesis:r${round}`, schema: SYNTH_VERDICTS_SCHEMA }))
    return out || null
  }

  // the code-fixer (fixStep): attempt every blocking finding, commit fixes, tag upstream-traced blockers.
  const fixStep = async (fixContext, verdict, runDir) => {
    const prompt =
      `You are the code-fixer. ${FIX_RESULT_INSTRUCTION} Attempt every blocking finding from the worklist, commit fixes, tag upstream-traced blockers. ` +
      `Never edit the review-loop machinery. Fix context:\n${JSON.stringify(fixContext)}${targetSuffix}`
    const iEngine = enginePrefTwin.resolveEngine('fix', _enginePrefs())
    if (iEngine !== 'claude') {
      const eff = enginePrefTwin.resolveEffort(iEngine, 'fix', _effortOverrides())
      const res = await engineDispatch.dispatchExternal({
        workItem: 'review-code', engine: iEngine, roleKind: 'fix', effort: eff, prompt,
        cwd: (target.worktree || procCwd()), schema: FIX_RESULT_SCHEMA,
      })
      if (res && res.ok) return normalizeFixResult({ fixed: [], deferred: [], changedSubjects: [], coverageDecisions: [] }, fixContext)
      const out = await agent(prompt, withModel(tiers.fixer, { label: `fix-code:r${verdict.round}`, schema: FIX_RESULT_SCHEMA }))
      return normalizeFixResult(out, fixContext)
    }
    const out = await agent(prompt, withModel(tiers.fixer, { label: `fix-code:r${verdict.round}`, schema: FIX_RESULT_SCHEMA }))
    return normalizeFixResult(out, fixContext)
  }

  const recordDeferred = async (report, _verdict, runDir) => {
    // #115: write the deferred-set via the cheap exec dumb-pipe (not a genuine agent). record_deferred.py
    // (frozen) appends the deferred identities to deferred-set.json — the channel the in-process tally
    // reads — and prints the readout-enrichment extras (fixes + accumulated parentOrigin) to stdout.
    const out = await exec([
      `python3 ${libPath('record_deferred.py')} --run-dir ${shq(runDir)} ` +
      `--report ${shq(JSON.stringify(report || {}))}`,
    ], 'record deferred')
    // Attach the computed extras to the fix report so #104's shared shell threads it
    // (report.extras -> tally -> readout). FR-6. Parse the cheap pipe's stdout (best-effort).
    let parsed = null
    // enrichment-only: a parse miss silently drops the readout extras (fixes + parentOrigin). No
    // control-flow rides on this (the deferred-set is the script's own file write), but log it so the
    // dropped enrichment is observable.
    try { parsed = JSON.parse((out && out[0] && out[0].stdout) || '') }
    catch (_) { try { log(`recordDeferred: could not parse record_deferred.py extras — readout enrichment dropped`) } catch (_e) {} }
    if (parsed && parsed.extras && report && typeof report === 'object') report.extras = parsed.extras
  }

  return { reviewerAgent, synthesisLeaf, fixStep, recordDeferred }
}

// Drive the shared loop with the code-review configuration + leaves (FR-1..FR-5, FR-7, FR-8).
async function runReviewCodePanel({ runDir, context, rubric, verifyCommand, leaves, worktree, preloaded }) {
  globalThis.reviewerAgent = leaves.reviewerAgent
  globalThis.synthesisLeaf = leaves.synthesisLeaf
  globalThis.recordDeferred = leaves.recordDeferred
  return withTargetCommandPrompts(worktree, () => reviewPanel({
    reviewerSet: REVIEW_CODE_REVIEWERS,
    context, rubric, runKey: runDir, runDir,
    fixStep: leaves.fixStep,
    maxRounds: 7,
    legKind: { panel: true, code: true },
    verifyCommand,
    preloaded,
  }))
}

module.exports = { REVIEW_CODE_REVIEWERS, normalizeFixResult, _policyChangedSubjects }

// The plan/tasks doc-review panel (the five reviewers, unchanged by #34 — spec Assumptions).
const DOC_REVIEWERS = ['architecture-reviewer', 'code-reviewer', 'security-reviewer',
                       'test-reviewer', 'premortem-reviewer']

// the three caller-supplied doc-leg leaf wrappers the #104 shell expects (panel:true). Each is a
// single leaf (no fan-out). Set as globalThis.* before reviewPanel, exactly as runReviewCodePanel does.
// #115: the reviewer RETURNS a findings[] array (the panel holds it in memory); the merge is the
// in-process panel_tally.compileFindings twin (no docMergeAgent / front_half.py merge), and the
// synthesis leaf RETURNS its keep/drop verdicts (loop_synthesis.consume reads them).
async function docReviewerAgent(reviewer, context, rubric, runDir, round, opts = {}) {
  const overrides = (typeof globalThis !== 'undefined' && globalThis.__SR_OVERRIDES) || null
  const model = modelTierTwin.resolveModel('reviewer', overrides, null)
  const promptContext = Object.assign({}, context || {}, {
    roundKind: opts.roundKind,
    coverageDecisions: opts.coverageDecisions || [],
    receiptArtifact: opts.receiptArtifact,
    receiptCoverageDecisionIds: (opts.coverageDecisions || []).map((d) => d.id).filter(Boolean),
  })
  const out = await agent(
    `Run the ${reviewer} review of the ${context.docType} definition-doc at ${context.docPath} ` +
    `against the ${rubric} rubric (reframed to a ${context.docType} doc). ${REVIEW_DOC_ARTIFACT_READ_INSTRUCTION} ${REVIEWER_RESULT_INSTRUCTION}${reviewerRetryCorrection(opts.retryReason)}\n\n` +
    `Prompt context: ${JSON.stringify(promptContext)}`,
    Object.assign({ model }, { label: reviewer, schema: FINDINGS_SCHEMA }))
  if (!out || !Array.isArray(out.findings)) return null
  return ensureReviewerShape(out, Object.assign({}, opts, { round }))
}
async function docSynthesisLeaf(merged, context, rubric, runDir, round) {
  const overrides = (typeof globalThis !== 'undefined' && globalThis.__SR_OVERRIDES) || null
  const model = modelTierTwin.resolveModel('synthesis', overrides, null)
  const out = await agent(
    `You are the panel synthesis judge for round ${round} of the ${context.docType} doc review. ` +
    `For each merged finding below and the doc at ${context.docPath}, per the synthesis-leaf prompt ` +
    `(plugins/superheroes/eval/synthesis-leaf.md) emit one keep/drop/severity verdict (keep-on-uncertain). ` +
    `Return ONLY a JSON object {"verdicts":[{"id","action":"keep|drop","reason","severity"}]} keyed by ` +
    `each finding's file::normalized-title identity.\n\nMerged findings:\n${JSON.stringify(merged)}`,
    Object.assign({ model }, { label: `synthesis:r${round}`, schema: SYNTH_VERDICTS_SCHEMA }))
  return out || null
}
async function saveRoundStateBestEffort(workItem, doc, round, deferred, runDir) {
  const state = { workItem, doc, round, deferred }
  const script = [
    'import json, os, sys',
    'payload = json.loads(sys.argv[1])',
    'run_dir = sys.argv[2]',
    'os.makedirs(run_dir, exist_ok=True)',
    'path = os.path.join(run_dir, "round-state.json")',
    'with open(path, "w", encoding="utf-8") as fh:',
    '    json.dump(payload, fh, sort_keys=True)',
    'print(json.dumps({"ok": True, "path": path}))',
  ].join('\n')
  try {
    await courier.runCourierJson(
      'save round state',
      `python3 -c ${shq(script)} ${shq(JSON.stringify(state))} ${shq(runDir)}`,
      { require: ['ok'], retryRealFailure: false },
    )
  } catch (_) {}
}

async function docRecordDeferred(report, verdict, runDir, context, runtimeDeferred) {
  // #115: write the deferred-set via the cheap exec dumb-pipe. fix-report.json is a transient hand-off
  // written first, then front_half.py record-deferred (frozen) appends the deferred identities to
  // deferred-set.json — the channel the in-process tally reads. Both run as cheap pipes.
  await io().writeFile(`${runDir}/fix-report.json`, JSON.stringify(report || {}))
  const results = await exec([
    `python3 ${libPath('front_half.py')} record-deferred --run-dir ${shq(runDir)} ` +
    `--report ${shq(runDir + '/fix-report.json')}`,
  ], 'record deferred')
  for (const item of (report && report.deferred) || []) {
    const id = item && (item.identity || item.id)
    if (!id) continue
    runtimeDeferred.set(String(id), item.severity || 'Critical')
  }
  // A failed deferred-set write under-counts deferrals (a finding could re-block); surface it.
  // No park: an under-count is itself fail-closed (a finding stays blocking; the loop doesn't falsely exit).
  if (!(results && results[0] && results[0].ok)) {
    try { log(`docRecordDeferred: deferred-set write may have failed for ${runDir} (under-count risk)`) } catch (_) {}
  }
}

// the doc-reviser fixStep: dispatch the doc-reviser leaf; return the resolved/deferred report
// (with extras.parentOrigin for a parent-traced / GATE finding), or null on failure (#104 -> halted).
async function docReviser(fixContext, verdict, runDir, context) {
  const overrides = (typeof globalThis !== 'undefined' && globalThis.__SR_OVERRIDES) || null
  const model = modelTierTwin.resolveModel('fixer', overrides, 'doc')
  const out = await agent(
    `You are the doc-reviser (fixStep) for the ${context.docType} doc at ${context.docPath}. ` +
    `${FIX_RESULT_INSTRUCTION} Per plugins/superheroes/eval/doc-reviser-leaf.md resolve blocking findings. ` +
    `Fix context:\n${JSON.stringify(fixContext)}`,
    Object.assign({ model }, { label: 'revise-doc', schema: FIX_RESULT_SCHEMA }))
  return normalizeFixResult(out, fixContext)
}

// run the panel-doc leg: set the four global wrappers, then reviewPanel with the front-half wiring.
async function runReviewDocPanel({ workItem, docType, docPath, runDir, runtimeDeferred, preloaded }) {
  const context = { workItem, docType, docPath }
  // fold 2 (#141): with a preloaded gather the deferred-set seed was already read (and runtimeDeferred
  // seeded by the caller) inside the one gather leaf — don't re-read it here. Only the unfolded
  // fallback path (gather failed / a direct smoke) does its own seed read.
  if (!preloaded && runtimeDeferred && runtimeDeferred.size === 0) {
    // Deliberate degrade: a courier prose-flake on deferred-set reads as {} — worst case a
    // deferred finding re-blocks or gets re-reviewed (waste, not corruption).
    const saved = await io().readJson(`${runDir}/deferred-set.json`, {})
    for (const id of Object.keys(saved || {})) runtimeDeferred.set(id, saved[id])
  }
  globalThis.reviewerAgent = docReviewerAgent
  globalThis.synthesisLeaf = docSynthesisLeaf
  globalThis.recordDeferred = (report, verdict, rd) =>
    docRecordDeferred(report, verdict, rd, context, runtimeDeferred || new Map())
  return reviewPanel({
    reviewerSet: DOC_REVIEWERS, context, rubric: 'review-base', runKey: runDir, runDir,
    fixStep: (fixContext, verdict, rd) => docReviser(fixContext, verdict, rd, context),
    maxRounds: 7, legKind: { panel: true, code: false }, verifyCommand: 'none', preloaded })
}

module.exports.DOC_REVIEWERS = DOC_REVIEWERS
module.exports.runReviewDocPanel = runReviewDocPanel

// docDirFor: the work-item's docs dir, storage-mode-aware. showrunner() resolves it ONCE at
// startup (readStartupState runs definition_doc.resolve_work_item_dir Python-side — correct for
// in-repo AND out-of-repo storage, main checkout and linked worktrees) and plants the absolute
// dir on globalThis.__SR_DOC_DIRS keyed by work-item. Un-planted (direct smoke/unit drives, or a
// failed resolution) falls back to the legacy in-repo default. Sync on purpose: no per-call
// courier leaf (#118 bar — 0-or-1 leaf per stretch).
function docDirFor(workItem) {
  const m = (typeof globalThis !== 'undefined' && globalThis.__SR_DOC_DIRS) || null
  const d = (m && typeof m === 'object') ? m[workItem] : null
  return (typeof d === 'string' && d) ? d : `docs/superheroes/${workItem}`
}
function docPathFor(workItem, doc) { return `${docDirFor(workItem)}/${doc}.md` }
function runDirFor(workItem, phase) { return `/tmp/showrunner-${workItem}-${phase}` }

// UFR-2: a failed external author-plan may have edited the doc and/or stamped the completion
// marker; discard both before falling open to the native author so an unaudited external draft
// cannot pass the post-check usableDraft gate.
async function _resetAuthorPlanDraft(workItem, doc) {
  const dir = docDirFor(workItem)
  const docPath = `${dir}/${doc}.md`
  const markerPath = `${dir}/.${doc}.complete`
  const root = checkoutRoot()
  const cmd = (root && !String(dir).startsWith('/'))
    ? selfContained(
      `rm -f ${shq(markerPath)} && (git checkout -- ${shq(docPath)} 2>/dev/null || rm -f ${shq(docPath)})`)
    : `rm -f ${shq(markerPath)} ${shq(docPath)}`
  await exec([cmd], 'reset author-plan draft')
}

// author-plan confinement: snapshot git status --porcelain via the exec courier.
async function _snapshotGitPorcelain() {
  const results = await exec([selfContained('git status --porcelain')], 'author-plan git snapshot')
  if (!results || !results[0] || !results[0].ok) return null
  return results[0].stdout || ''
}

function _parsePorcelain(text) {
  const entries = new Map()
  if (!text) return entries
  for (const line of String(text).split('\n')) {
    if (!line.trim()) continue
    const code = line.slice(0, 2)
    let path = line.slice(3).trim()
    const arrow = path.indexOf(' -> ')
    if (arrow >= 0) path = path.slice(arrow + 4)
    if (path) entries.set(path, code)
  }
  return entries
}

// Normalize a porcelain or filesystem path to checkout-root-relative form for comparison.
function _normalizeComparePath(path) {
  let p = String(path).replace(/^\.\//, '')
  const root = checkoutRoot()
  if (root) {
    const r = String(root).replace(/\/$/, '')
    if (p === r) return ''
    if (p.startsWith(r + '/')) return p.slice(r.length + 1)
  }
  return p
}

// author-plan confinement allowlist: only the plan doc's own artifacts (exact paths, not prefix).
function _authorPlanArtifactPaths(workItem) {
  const dir = _normalizeComparePath(docDirFor(workItem))
  return [`${dir}/plan.md`, `${dir}/.plan.complete`]
}

function _pathIsAuthorPlanArtifact(path, workItem) {
  return _authorPlanArtifactPaths(workItem).includes(_normalizeComparePath(path))
}

// Top-level checkout-relative docs tree for confinement scan (e.g. 'docs'). Skipped when the
// work-item doc dir resolves outside the checkout (out-of-repo storage).
function _docsScanRoot(workItem) {
  const dir = docDirFor(workItem)
  const root = checkoutRoot()
  if (String(dir).startsWith('/')) {
    if (!root) return null
    const r = String(root).replace(/\/$/, '')
    if (!String(dir).startsWith(r + '/')) return null
  } else if (!root) {
    return null
  }
  const rel = _normalizeComparePath(dir)
  if (!rel) return null
  const seg = rel.split('/')[0]
  return seg || null
}

function _parseFileList(text) {
  const set = new Set()
  if (!text) return set
  for (const line of String(text).split('\n')) {
    const p = line.trim()
    if (p) set.add(_normalizeComparePath(p))
  }
  return set
}

async function _snapshotDocsFileList(docsRoot) {
  const results = await exec([selfContained(`find ${shq(docsRoot)} -type f | sort`)], 'author-plan docs snapshot')
  if (!results || !results[0] || !results[0].ok) return null
  return results[0].stdout || ''
}

async function _snapshotDocsNewer(docsRoot, stampPath) {
  const results = await exec(
    [selfContained(`find ${shq(docsRoot)} -type f -newer ${shq(stampPath)} | sort`)],
    'author-plan docs newer')
  if (!results || !results[0] || !results[0].ok) return null
  return results[0].stdout || ''
}

function _docsStampPath(workItem) {
  return `/tmp/showrunner-docs-${safeRunKey(workItem)}.stamp`
}

// Gitignored docs-tree confinement: detect new/modified files under docsRoot that porcelain misses.
async function _scanAndRevertDocsStrays(workItem, docsRoot, stampPath, beforeText) {
  if (beforeText == null) return { strayPaths: [], unconfined: true }
  const afterText = await _snapshotDocsFileList(docsRoot)
  if (afterText == null) return { strayPaths: [], unconfined: true }
  const newerText = await _snapshotDocsNewer(docsRoot, stampPath)
  if (newerText == null) return { strayPaths: [], unconfined: true }
  const before = _parseFileList(beforeText)
  const after = _parseFileList(afterText)
  const newer = _parseFileList(newerText)
  const newStrays = []
  const modifiedStrays = []
  for (const p of after) {
    if (_pathIsAuthorPlanArtifact(p, workItem)) continue
    if (!before.has(p)) newStrays.push(p)
  }
  for (const p of newer) {
    if (_pathIsAuthorPlanArtifact(p, workItem)) continue
    if (before.has(p)) modifiedStrays.push(p)
  }
  if (modifiedStrays.length > 0) {
    return { strayPaths: [], unconfined: true, modifiedPaths: modifiedStrays }
  }
  if (newStrays.length === 0) return { strayPaths: [] }
  const revertCmds = newStrays.map((p) => selfContained(`rm -f -- ${shq(p)}`))
  const results = await exec(revertCmds, 'author-plan revert docs strays')
  if (!results || results.some((r) => !r || !r.ok)) return { strayPaths: [], unconfined: true }
  const postText = await _snapshotDocsFileList(docsRoot)
  if (postText == null) return { strayPaths: [], unconfined: true }
  const post = _parseFileList(postText)
  for (const p of newStrays) {
    if (!before.has(p) && post.has(p)) return { strayPaths: [], unconfined: true }
  }
  return { strayPaths: newStrays }
}

// After an external author-plan dispatch, revert checkout paths that newly dirtied outside the
// work-item doc dir during the dispatch window. Pre-existing dirty paths are never touched.
// A null snapshot (courier flake) on EITHER side makes strays indistinguishable from the user's
// own pre-existing edits — revert NOTHING and report unconfined (the caller fails the dispatch
// closed to the native author). Reverting against an empty "before" would checkout-revert the
// user's own uncommitted work.
async function _revertAuthorPlanStrays(workItem, beforeText, afterText) {
  if (beforeText == null || afterText == null) return { strayPaths: [], unconfined: true }
  const before = _parsePorcelain(beforeText)
  const after = _parsePorcelain(afterText)
  const strays = []
  for (const [p, code] of after) {
    if (_pathIsAuthorPlanArtifact(p, workItem)) continue
    if (before.has(p)) continue
    strays.push({ path: p, untracked: code === '??' || code[0] === '?' })
  }
  if (strays.length === 0) return { strayPaths: [] }
  const revertCmds = strays.map(({ path, untracked }) =>
    untracked ? selfContained(`rm -rf -- ${shq(path)}`) : selfContained(`git checkout -- ${shq(path)}`))
  const results = await exec(revertCmds, 'author-plan revert strays')
  if (!results || results.some((r) => !r || !r.ok)) return { strayPaths: [], unconfined: true }
  const postSnap = await _snapshotGitPorcelain()
  if (postSnap == null) return { strayPaths: [], unconfined: true }
  const post = _parsePorcelain(postSnap)
  for (const { path } of strays) {
    if (!before.has(path) && post.has(path)) return { strayPaths: [], unconfined: true }
  }
  return { strayPaths: strays.map((s) => s.path) }
}

// Stamp the content-bound completion marker after external author-plan confinement passes.
async function _stampAuthorPlanMarker(workItem, doc) {
  const cmd = selfContained(
    `python3 ${libPath('front_half_usable.py')} --work-item ${shq(workItem)} ` +
    `--doc ${shq(doc)} --write-marker --root "$(git rev-parse --show-toplevel)"`)
  const results = await exec([cmd], 'author-plan write marker')
  if (!results || !results[0] || !results[0].ok) return false
  try { return !!JSON.parse(results[0].stdout || '').wrote } catch (_) { return false }
}

function _draftContentReady(signals) {
  if (!signals || !signals.expected) return false
  const missing = Array.isArray(signals.missing_sections) ? signals.missing_sections : []
  return missing.length === 0 && !signals.placeholder
}

// the produce phase: author the doc author-only (resume a usable draft; re-produce otherwise).
// #115 Task 12: usableDraft uses exec+JS twin (front_half.isUsableDraft, no LLM agent).
// authorModel is the in-process JS twin (model_tier.resolveModel, no agent dispatch).
// The --write-marker stamp is FOLDED into the native author agent (FR-4 fold): the author's
// prompt instructs it to run front_half_usable.py --write-marker after authoring the doc.
// The EXTERNAL author-plan path omits --write-marker from the dispatch prompt; showrunner
// stamps the marker via exec ONLY after confinement passes and doc content verifies, so a
// crash before the stamp resumes into re-produce rather than accepting an unconfined draft.
// Layer 2b: bounded repair loop (N=2 retries, 3 total attempts). On a failed post-check the
// author is re-dispatched with a TARGETED gap hint derived from the --emit-signals why-signal
// (missing_sections + placeholder). Only parks (confidence:'low') after all attempts exhausted.
// NOTIFY defaults are accumulated across all attempts (not dropped on a failed attempt).
const _PRODUCE_MAX_RETRIES = 2   // N=2 retries -> 3 total author attempts
async function producePhase(phase, workItem) {
  const doc = phase                                    // 'plan' | 'tasks'
  // resume vs re-produce: a usable draft (content-bound completion signal + complete content) is kept.
  const draft = await usableDraft(workItem, doc)
  if (draft.usable) return { confidence: 'high', assumptions: [] } // FR-8 resume — do not re-author
  const model = authorModel(doc)
  // planAuthor engine route: ONLY the plan doc reads the enginePreferences.planAuthor key (tasks
  // always authors native). The resolved model tier rides along so cursor can map it to its own
  // model id (author-plan: fable + planAuthor: cursor = Fable via Cursor). External failure falls
  // open to the native author within the same attempt — the usableDraft post-check is unchanged.
  const aEngine = doc === 'plan'
    ? enginePrefTwin.resolveEngine('author-plan', _enginePrefs())
    : 'claude'
  // _authorPrompt: builds the author dispatch prompt. On a retry, appends a targeted gap hint so
  // the author knows precisely what to fix (Layer 2b). The hint is derived from the why-signal
  // (missing_sections + placeholder) returned by usableDraft on the previous failed check.
  // FR-8 sandbox: no banned tokens in this function body.
  function _authorPrompt(gapSignal, includeWriteMarker) {
    let base =
      `You are the author-only produce leaf (plugins/superheroes/eval/produce-leaf.md). Author the ` +
      `${doc} definition-doc for work-item ${workItem} from its approved parent, every section ` +
      `non-empty, no placeholder.`
    if (includeWriteMarker !== false) {
      base +=
        ` After writing the doc, run the following command to stamp the ` +
        `content-bound completion marker (deterministic — do NOT skip it):\n\n` +
        selfContained(`python3 ${libPath('front_half_usable.py')} --work-item ${shq(workItem)} ` +
        `--doc ${shq(doc)} --write-marker --root "$(git rev-parse --show-toplevel)"`) + `\n\n`
    }
    base +=
      `Do NOT run review or record the review gate. Return ` +
      `{ status, notify } where notify is an array of any NOTIFY-class defaults you took, each ` +
      `{ identity, message }.`
    if (!gapSignal) return base
    const hints = []
    const missing = (gapSignal.missing_sections && Array.isArray(gapSignal.missing_sections))
      ? gapSignal.missing_sections : []
    if (missing.length > 0) {
      hints.push(
        `Your previous draft was rejected: the following required sections must be ## markdown headings ` +
        `with non-empty content: ${missing.join(', ')}. ` +
        `Use "## ${missing[0]}" (a heading), NOT "**${missing[0]}:**" (bold inline label).`)
    }
    if (gapSignal.placeholder) {
      hints.push(`A placeholder token was found (e.g. TBD, {{…}}, or "similar to Task N") — remove it.`)
    }
    if (hints.length === 0) return base
    return base + `\n\nIMPORTANT (retry): ` + hints.join(' ')
  }
  // Bounded author+repair loop: up to _PRODUCE_MAX_RETRIES retries (3 total attempts).
  // lastSignal carries the why-signal from the previous failed check for the gap hint.
  let lastSignal = null
  for (let attempt = 0; attempt <= _PRODUCE_MAX_RETRIES; attempt++) {
    const gapSignal = attempt > 0 ? lastSignal : null
    let authored = null
    if (aEngine !== 'claude') {
      // External author-plan: no --write-marker in the dispatch prompt; showrunner stamps after confinement.
      const extPrompt = _authorPrompt(gapSignal, false)
      const eff = enginePrefTwin.resolveEffort(aEngine, 'author-plan', _effortOverrides())
      const beforeSnap = await _snapshotGitPorcelain()
      const docsRoot = _docsScanRoot(workItem)
      let beforeDocs = null
      let docsStamp = null
      if (docsRoot) {
        docsStamp = _docsStampPath(workItem)
        const stampRes = await exec([`touch ${shq(docsStamp)}`], 'author-plan docs stamp')
        if (!stampRes || !stampRes[0] || !stampRes[0].ok) beforeDocs = null
        else beforeDocs = await _snapshotDocsFileList(docsRoot)
      }
      const res = await engineDispatch.dispatchExternal({
        workItem, engine: aEngine, roleKind: 'author-plan', effort: eff, prompt: extPrompt,
        cwd: checkoutRoot() || procCwd(), model,
      })
      const afterSnap = await _snapshotGitPorcelain()
      const porcelainResult = await _revertAuthorPlanStrays(workItem, beforeSnap, afterSnap)
      const docsResult = (docsRoot && docsStamp)
        ? await _scanAndRevertDocsStrays(workItem, docsRoot, docsStamp, beforeDocs)
        : { strayPaths: [], unconfined: false }
      const unconfined = porcelainResult.unconfined || docsResult.unconfined
      const strayPaths = [...porcelainResult.strayPaths, ...docsResult.strayPaths]
      if (strayPaths.length || unconfined) {
        if (typeof globalThis.log === 'function') {
          if (docsResult.modifiedPaths && docsResult.modifiedPaths.length) {
            globalThis.log('author-plan: modified ignored docs (unconfined): ' + docsResult.modifiedPaths.join(', '))
          }
          globalThis.log(unconfined
            ? 'author-plan: confinement snapshot unavailable — external draft discarded (nothing reverted)'
            : 'author-plan: stray checkout edits reverted: ' + strayPaths.join(', '))
        }
        await _resetAuthorPlanDraft(workItem, doc) // confinement failure -> fall open to native
      } else if (res && res.ok) {
        const draftNow = await usableDraft(workItem, doc)
        if (_draftContentReady(draftNow)) {
          const stamped = await _stampAuthorPlanMarker(workItem, doc)
          const afterStamp = stamped ? await usableDraft(workItem, doc) : { usable: false }
          if (afterStamp.usable) authored = { status: 'ok', notify: res.notify || [] }
          else await _resetAuthorPlanDraft(workItem, doc)
        } else {
          await _resetAuthorPlanDraft(workItem, doc) // unusable external draft -> fall open to native
        }
      } else {
        await _resetAuthorPlanDraft(workItem, doc) // UFR-2: discard external draft before fall-open
      }
    }
    if (authored == null) {
      // FR-4 fold (native only): the author leaf writes its own doc + stamps the completion marker.
      const nativePrompt = _authorPrompt(gapSignal, true)
      authored = await agent(
        nativePrompt,
        { label: `author-${doc}`, model,
          schema: { type: 'object', properties: { status: {}, notify: { type: 'array' } } } })
    }
    if (authored == null) {
      return { confidence: 'low', assumptions: [`produce step failed for ${doc}`] } // UFR-4
    }
    // surface any produce-phase NOTIFY default in the durable ledger the boundary reads (UFR-2): a
    // produce phase has no #104 loop record to ride, so it is named via the ledger, not the extras seam.
    // NOTIFY defaults are recorded on EVERY attempt (not dropped on a failed check — UFR-2).
    if (authored.notify && authored.notify.length) {
      const ok = await appendNotify(workItem, authored.notify.map(
        (n) => ({ phase: doc, identity: n && n.identity, message: n && n.message })))
      if (!ok) {
        // a NOTIFY default that can't be durably recorded must NOT be silently lost (UFR-2): park and
        // name it. No marker is stamped yet, so a resume re-produces and retries the NOTIFY.
        return { confidence: 'low', assumptions: ['produce NOTIFY default not durably recorded: ' +
                 authored.notify.map((n) => (n && n.message) || '').join('; ')] }
      }
    }
    // Verify the author actually stamped the marker (UFR-4 guard). usableDraft re-reads via exec+twin.
    // The why-signal (missing_sections, placeholder) is preserved for the next retry's gap hint.
    const after = await usableDraft(workItem, doc)
    if (after.usable) return { confidence: 'high', assumptions: [] }
    // Store the gap signal for the next attempt's targeted hint.
    lastSignal = after
    // If more retries remain, loop back and re-dispatch the author with the gap hint.
    // On the last attempt, fall through to park.
  }
  // All attempts exhausted — park low-confidence, naming the persistent gap.
  const gapDesc = (lastSignal && lastSignal.missing_sections && lastSignal.missing_sections.length)
    ? `missing ## headings: ${lastSignal.missing_sections.join(', ')}`
    : (lastSignal && lastSignal.placeholder ? 'placeholder token present' : 'content check failed')
  return { confidence: 'low',
    assumptions: [`produce step yielded no usable ${doc} draft after ${_PRODUCE_MAX_RETRIES + 1} attempts: ${gapDesc}`] }
}

// the review phase: idempotent passed-gate skip, else run the panel-doc leg and map terminal->gate.
// #115 Task 12: gateForTerminal is now the in-process JS twin. #118: the gate write rides the
// per-phase 'save phase progress' tail in runPhases (set-gate chained ahead of journal+checkpoint)
// — this phase returns the persist spec, it does not dispatch the write itself.
async function reviewDocPhase(doc, workItem, opts) {
  opts = opts || {}
  const runId = opts.runId || `review-${doc}-${workItem}`
  const lease = opts.lease || undefined
  const existing = await readGate(workItem, doc)
  if (existing === 'passed') {
    // cursor-lost re-entry guard (gate written, tail persist failed): never re-run the panel and
    // risk overwriting a correct passed (FR-8 passed-gate skip).
    return { phaseResult: { confidence: 'high', assumptions: [] }, gate: 'passed' }
  }
  const runDir = runDirFor(workItem, `review-${doc}`)
  const docPath = docPathFor(workItem, doc)
  // fold 2 (#141; #211 decision shape): ONE gather leaf does the run-dir mkdir + deferred-set seed +
  // resume DECISION + round-1 plan + entry coverage read (no records ride up). Seed runtimeDeferred
  // from it and hand it to the panel as `preloaded`. A gather transport failure -> null: fall back to
  // a plain mkdir and let the panel read its own entry state (correct, just unfolded).
  const setup = await gatherReviewSetup({
    runDir, reviewerSet: DOC_REVIEWERS, context: { workItem, docType: doc, docPath },
    legKind: { panel: true, code: false }, ioApi: io(),
  })
  if (!setup) await io().mkdirp(runDir)
  const deferred = new Map()
  if (setup) for (const id of Object.keys(setup.deferredSet || {})) deferred.set(id, setup.deferredSet[id])
  const verdict = await runReviewDocPanel({
    workItem,
    docType: doc,
    docPath,
    runDir,
    runtimeDeferred: deferred,
    preloaded: setup || undefined,
  })
  await saveRoundStateBestEffort(
    workItem,
    doc,
    (verdict && verdict.round) || 1,
    Array.from(deferred.entries()).map(([id, severity]) => ({ id, severity })),
    runDir,
  )
  // persist the #104 terminal record so the front-half boundary can embed its readout (FR-7).
  // The record is composed PYTHON-SIDE from the run's on-disk state (round-records.json +
  // review-telemetry.json); only the small verdict scalars ride inline (self-verified), so the
  // ~14KB evidence-bodied verdict never crosses a courier writeFile — the payload-stage-failed
  // park class (live 2026-07-02, run wf_94c879e0-747). Overwrite is finalize's job: the record
  // is durable for crash-resume, not append-only (the lease serializes live sessions).
  // gateForTerminal is the in-process JS twin (no agent dispatch).
  const gate = gateForTerminal(verdict && verdict.terminal)
  // The set-gate fence hash is computed PYTHON-SIDE at write time ('current' sentinel), never
  // from a courier read: in the sandbox a readText of a missing/odd file answers PROSE (live
  // 2026-07-02, 4 consecutive runs), and contentHash(prose) poisons the fence into a permanent
  // 'stale' park. The runtime makes no decision between its old re-read and the write, so the
  // sentinel loses only same-window concurrent-edit detection (the lease excludes that) —
  // and definition_doc.py resolves + hashes the SAME file it edits (doc-dir aware), so no
  // runtime-resolved hash can disagree with the write target.
  const reviewedHash = 'current'
  // #118 "Every phase" tail: gate + journal + checkpoint land in ONE 'save phase progress' leaf,
  // dispatched by runPhases' tail with the REAL step index — NOT persisted here (the old
  // step:-1 pre-persist plus runPhases' journal/cursor writes was the FR-6 double-journal, and
  // the transient step:-1 checkpoint could regress a crash-resume to phase 0). This phase hands
  // the tail its set-gate side-effect command + journal payload; a failed persist parks there
  // (UFR-5 — the run never advances on an un-recorded gate).
  const leaseArg = lease ? ` --lease ${shq(lease)}` : ''
  const sideEffectCmd =
    `python3 ${libPath('definition_doc.py')} set-gate --doc ${shq(doc)} ` +
    `--work-item ${shq(workItem)} --review ${shq(gate)} --root "$(git rev-parse --show-toplevel)" ` +
    `--expected-hash ${shq(reviewedHash)} --run-id ${shq(runId)}${leaseArg}`
  const persist = {
    sideEffectCmd,
    journalPayload: { phase: `review-${doc}`, gate, confidence: 'high', assumptions: [], runId, lease },
  }
  const recPath = `${runDir}/terminal-record.json`
  const recWrite = await writeTerminalRecord(recPath, verdict || {}, { runId, lease, runDir })
  if (verdict && verdict.reason === 'round-memory-unreadable') {
    return {
      phaseResult: {
        confidence: 'low',
        assumptions: ['round-memory-unreadable'],
        parkReason: 'round-memory-unreadable',
      },
      gate: null,
      runtimeDeferredIds: Array.from(deferred.keys()),
    }
  }
  if (!recWrite.ok) {
    if (gate === 'passed') {
      return {
        phaseResult: { confidence: 'high', assumptions: [] },
        gate,
        persist,
        runtimeDeferredIds: Array.from(deferred.keys()),
      }
    }
    return {
      phaseResult: {
        confidence: 'low',
        assumptions: [`terminal-record.json ${recWrite.reason || 'write-failed'} for ${doc}`],
        parkReason: `terminal-record.json ${recWrite.reason || 'write-failed'} for ${doc}`,
      },
      gate,
      runtimeDeferredIds: Array.from(deferred.keys()),
    }
  }
  // #212: on a non-passed gate, name the terminal + the panel's honest reason on parkDetail so the
  // workflow park survives the phase-layer flatten (phase_step threads it into the changes-requested
  // reason). A passed gate proceeds — no park detail.
  const phaseResult = { confidence: 'high', assumptions: [] }
  if (gate !== 'passed') {
    phaseResult.parkDetail = `${(verdict && verdict.terminal) || 'cannot-certify'}: ${(verdict && verdict.reason) || 'review not certified'}`
  }
  return {
    phaseResult,
    gate,
    persist,
    runtimeDeferredIds: Array.from(deferred.keys()),
  }
}

// gateForTerminal: pure in-process JS twin. No agent dispatch.
function gateForTerminal(terminal) {
  return frontHalfTwin.gateForTerminal(terminal || 'unknown')
}

// usableDraft: exec runs front_half_usable.py --emit-signals, which computes the verdict
// Python-side at the IO boundary (calls front_half.is_usable_draft) and returns a small
// {usable, recorded, expected, missing_sections, placeholder} signal — the large doc text
// never crosses the cheapest-model pipe (live-surfaced large-payload-transport limit).
// The frontHalfTwin.isUsableDraft JS twin stays for parity testing only; it is no longer
// called here on the live doc text.
// Layer 2a: the why-signal fields (missing_sections, placeholder) are forwarded so the
// produce repair loop (producePhase) can craft a targeted gap hint for re-prompting.
async function usableDraft(workItem, doc) {
  const results = await exec([
    `python3 ${libPath('front_half_usable.py')} --work-item ${shq(workItem)} ` +
    `--doc ${shq(doc)} --root "$(git rev-parse --show-toplevel)" --emit-signals`,
  ], 'check draft')
  let signals = null
  try { signals = JSON.parse((results[0] && results[0].stdout) || '') } catch (_) {}
  if (!signals) return { usable: false }   // IO failure -> fail closed (re-produce)
  return {
    usable: !!signals.usable,
    expected: signals.expected || '',
    missing_sections: Array.isArray(signals.missing_sections) ? signals.missing_sections : [],
    placeholder: !!signals.placeholder,
  }
}

// authorModel: pure in-process JS twin. Reads overrides from globalThis.__SR_OVERRIDES (set by
// Task 17 startup pipe; absent in test/throwaway runs -> null -> DEFAULT_TIERS.author = 'opus').
// The plan doc resolves the split `author-plan` role (own override, e.g. fable, else exactly
// `author`); tasks stays on `author` — plan authoring alone can be raised without moving tasks.
function authorModel(doc) {
  const overrides = (typeof globalThis !== 'undefined' && globalThis.__SR_OVERRIDES) || null
  return modelTierTwin.resolveModel(doc === 'plan' ? 'author-plan' : 'author', overrides, null)
}

// #38: read globalThis.__SR_ENGINE_PREFS (planted once at startup — see showrunner()'s startup pipe).
// Absent/malformed -> the safe degenerate default (both roles on claude, no effort overrides).
function _enginePrefs() {
  const p = (typeof globalThis !== 'undefined' && globalThis.__SR_ENGINE_PREFS) || null
  return (p && typeof p === 'object') ? p : { reviewer: 'claude', implementation: 'claude', effort: {} }
}

// FR-9 effort overrides: the role_kind-keyed effort sub-map INSIDE __SR_ENGINE_PREFS (NOT the model-tier
// __SR_OVERRIDES map, which is keyed by role->model). resolveEffort reads this; absent -> null -> default.
function _effortOverrides() {
  const p = _enginePrefs()
  return (p && p.effort && typeof p.effort === 'object' && !Array.isArray(p.effort)) ? p.effort : null
}
// the durable per-work-item NOTIFY ledger (next to the docs — run-local state, never committed).
// Rides docDirFor, so it lands in the project store for an out-of-repo-calibrated project.
function notifyLedgerFor(workItem) { return `${docDirFor(workItem)}/.notify.json` }
// appendNotify: IO accumulator write via exec (not cmdRunner). Returns false on failed durable write.
async function appendNotify(workItem, entries) {
  const results = await exec([
    `python3 ${libPath('front_half.py')} append-notify ` +
    `--ledger ${shq(notifyLedgerFor(workItem))} --entries ${shq(JSON.stringify(entries || []))}`,
  ], 'append notify')
  let out = null
  try { out = JSON.parse((results[0] && results[0].stdout) || '') } catch (_) {}
  return !!(out && out.ok)   // false on a failed durable write — the caller must not silently lose it
}

module.exports.producePhase = producePhase
module.exports.reviewDocPhase = reviewDocPhase
module.exports.notifyLedgerFor = notifyLedgerFor
module.exports.docPathFor = docPathFor

// FR-7: compose the front-half run-outcome envelope (in-process via frontHalfTwin.renderRunOutcome)
// and return a parked result. Reads best-effort per-phase terminal records + the durable NOTIFY ledger.
// The ENVELOPE judgment is in-process (no front_half.py render-outcome agent); only the per-phase
// loop_readout RENDER stays an exec leaf (loop_readout.py --record <path>).
// #115 Task 18: rewired from 1 decider agent to 0 — envelope is the twin, readout stays exec.
async function frontHalfBoundary(workItem) {
  // The io() seam is async (it shares one contract with the bundle's Promise-returning leaf-bash io),
  // so await every read BEFORE building the outcome literal — embedding an un-awaited Promise would
  // serialize as "{}" and silently drop the durable readout records (the bug this fix class closes).
  const notify = await io().readJson(notifyLedgerFor(workItem), [])
  const planRec = await io().readJson(`${runDirFor(workItem, 'review-plan')}/terminal-record.json`, null)
  const tasksRec = await io().readJson(`${runDirFor(workItem, 'review-tasks')}/terminal-record.json`, null)
  const outcome = {
    completed_phases: ['plan', 'review-plan', 'tasks', 'review-tasks'],
    docs: { plan: docPathFor(workItem, 'plan'), tasks: docPathFor(workItem, 'tasks') },
    notify,
    phase_records: [
      { phase: 'review-plan', record: planRec },
      { phase: 'review-tasks', record: tasksRec },
    ],
    readout_record_ok: true,
  }
  // recordOk guards UFR-6: if we cannot write the durable readout records, flag it in the reason.
  // (The readout records live in the per-phase run dirs and are written by renderAndPostReadout earlier;
  // the outcome JSON written here is the durable ENVELOPE artifact — a missing write flags UFR-6.)
  // Overwrite mode with NO lease: this envelope is composed fresh from the durable per-phase
  // records on every boundary pass, so last-writer-wins between duplicate runs is accepted —
  // both writers derive near-identical content from the same records (see fenced_json.js).
  const outPath = `/tmp/showrunner-${workItem}-fronthalf-outcome.json`
  const runId = `fronthalf-${workItem}`
  const outcomeWrite = await fencedJsonWrite(outPath, outcome, { overwrite: true, runId })
  let recordOk = !!outcomeWrite.ok

  // exec-backed renderReadout: writes the record to a temp file and execs loop_readout.py --record.
  // Mirrors how renderAndPostReadout runs loop_readout.py (line ~896). Returns the stdout text.
  // Used only when recordOk (the write seam is available); if recordOk is false the loop body is
  // skipped (phase_records still embeds headers with no readout text — tolerable since UFR-6 fires).
  async function renderReadout(record) {
    const recPath = `/tmp/showrunner-${workItem}-fronthalf-readout-tmp.json`
    try { await io().writeFile(recPath, JSON.stringify(record || {})) } catch (_) { return '' }
    // dumb-pipe render via the courier (pinned cheapest + one-shot retry; rootedCommand = FR-5).
    try {
      const text = await courier.runCourierText(
        'readout',
        `python3 ${libPath('loop_readout.py')} --record ${shq(recPath)}`)
      return typeof text === 'string' ? text : ''
    } catch (_e) {
      return ''
    }
  }

  // In-process envelope composition (no agent for the judgment — only the per-phase readout is exec).
  // If the durable outcome JSON could not be written, skip phase_records embed (no readout seam) and
  // surface UFR-6 in the fallback reason instead; the twin still composes the envelope shell.
  const rendered = recordOk
    ? frontHalfTwin.renderRunOutcome(outcome, renderReadout)
    : frontHalfTwin.renderRunOutcome({ ...outcome, phase_records: [], readout_record_ok: false })

  // rendered is a Promise when renderReadout is async (it is, above) — await it.
  const text = await rendered

  const reason = (typeof text === 'string' && text.trim())
    ? text
    : recordOk
      ? 'front-half complete: plan and tasks gated — parked at the front-half boundary, awaiting owner'
      : '⚠️ front-half complete (plan and tasks gated) but the run-outcome record could not be written ' +
        '— treat the durable readout as missing (UFR-6); awaiting owner'
  return { outcome: 'parked', phase: 'front-half-boundary', reason }
}

module.exports.frontHalfBoundary = frontHalfBoundary

function shq(s) { return "'" + String(s).replace(/'/g, "'\\''") + "'" }
function safeRunKey(s) { return String(s).replace(/[^A-Za-z0-9_.-]+/g, '-').slice(0, 120) || 'target' }

// selfContained: FR-5 — prefix a command with `cd <root> && ` so the leaf always runs from the
// correct repo root, regardless of the haiku leaf's cwd. Opt-in: only applies when globalThis.__SR_ROOT
// is set (threaded from args.root in the ENTRY). Commands already starting with `cd ` (e.g. the
// build-worktree inWorktree commands) are left untouched — the startsWith guard prevents double-cd.
// When __SR_ROOT is unset (most smokes, back-half runs not yet opted in) behavior is unchanged.
function selfContained(cmd) {
  var root = checkoutRoot()
  if (!root) return cmd
  var trimmed = String(cmd).trimLeft ? String(cmd).trimLeft() : String(cmd).replace(/^\s+/, '')
  if (trimmed.startsWith('cd ')) return cmd   // already rooted (inWorktree or similar) — leave alone
  return 'cd ' + shq(root) + ' && ' + cmd
}

// checkoutRoot: the acquire-authority repo root threaded from recover_entry's snapshot (UFR-10).
// Planted on globalThis.__SR_ROOT after reconcile; bundle ENTRY may preset it from args.root.
function checkoutRoot(explicit) {
  if (explicit && String(explicit).trim()) return String(explicit)
  const r = (typeof globalThis !== 'undefined' && globalThis.__SR_ROOT)
    ? String(globalThis.__SR_ROOT) : null
  return (r && r.trim()) ? r : null
}

function fenceCliCmd(workItem, generation, root, extra) {
  const r = checkoutRoot(root)
  if (!r) return null
  return `python3 ${libPath('fence_cli.py')} --work-item ${shq(workItem)} ` +
    `--generation ${shq(String(generation))} --root ${shq(r)}${extra || ''}`
}

// cheapestModel: resolves the mechanical (cheapest) tier once and caches it. The `mechanical` tier
// is unconditionally `'haiku'` per DEFAULT_TIERS; resolving through model_tier.js keeps the twin
// parity contract intact and allows future overrides without changing the spine.
let _cheapestModelCache = null
function cheapestModel() {
  if (_cheapestModelCache === null) {
    _cheapestModelCache = require('./model_tier.js').DEFAULT_TIERS.mechanical
  }
  return _cheapestModelCache
}

// _parseExecResult: parse the leaf agent's response into a [{index,ok,stdout}] array.
// Handles all response shapes the leaf may produce:
//   1. Array (stub/pass-through) — returned as-is.
//   2. String — robust extraction tried in order:
//      (a) First fenced block ANYWHERE in the string (non-anchored match for prose-prefixed output).
//      (b) Whole trimmed string as-is (covers clean bare JSON array).
//      For each candidate, try JSON.parse directly; if that fails, slice from first '[' to last ']'
//      and JSON.parse that slice (handles prose before/after a bare JSON array).
//      The first candidate that yields an Array is returned.
//   3. Anything else / all candidates fail — synthetic per-command failure array (fail-closed).
// n = commands.length; used only for synthetic failure array sizing (must be >= 1).
function _parseExecResult(out, n) {
  var count = (n && n > 0) ? n : 1
  if (Array.isArray(out)) return out
  if (typeof out === 'string') {
    var trimmed = out.trim()
    // Build candidates to try, in priority order:
    // (a) content of the FIRST fenced block found anywhere (handles prose-prefixed fences).
    var candidates = []
    var fenceMatch = trimmed.match(/```(?:[a-zA-Z0-9]+)?\s*([\s\S]*?)```/)
    if (fenceMatch) candidates.push(fenceMatch[1].trim())
    // (b) whole trimmed string (handles clean bare JSON or prose-around-JSON via bracket slice).
    candidates.push(trimmed)
    for (var ci = 0; ci < candidates.length; ci++) {
      var candidate = candidates[ci]
      // Try direct parse first.
      try {
        var parsed = JSON.parse(candidate)
        if (Array.isArray(parsed)) return parsed
      } catch (_e1) { /* try bracket-slice fallback */ }
      // Slice from first '[' to last ']' to handle prose around a bare JSON array.
      var firstBracket = candidate.indexOf('[')
      var lastBracket = candidate.lastIndexOf(']')
      if (firstBracket >= 0 && lastBracket > firstBracket) {
        var slice = candidate.slice(firstBracket, lastBracket + 1)
        try {
          var sliced = JSON.parse(slice)
          if (Array.isArray(sliced)) return sliced
        } catch (_e2) { /* try next candidate */ }
      }
    }
  }
  // Synthetic per-command failure: callers can detect the failure and surface it clearly.
  var failures = []
  for (var i = 0; i < count; i++) {
    failures.push({ index: i, ok: false, stdout: 'exec: could not parse leaf result' })
  }
  return failures
}

// exec: the dumb-pipe executor. Dispatches ONE globalThis.agent whose prompt lists all fully-formed
// commands and asks the leaf to run each and return a JSON array of {index, ok, stdout}.
// The model is UNCONDITIONALLY forced to cheapestModel() — overriding __SR_LEAF_MODEL or any
// caller-supplied opts.model. This is a side-effect executor, not a genuine-LLM agent.
// `label` is a purely-cosmetic display purpose (e.g. 'read gate', 'prepare build') so the progress
// view names each leaf by what it does; it defaults to 'exec'. Dumb-pipe routing rides the structural
// `courier: true` marker (the bundle preamble's __isDumb pins cheapest off it, independent of the
// label), so a descriptive label never loosens the cheapest-model contract.
// FR-8 sandbox-safe: no fs, no child_process, no time/random globals, no process/bare-global refs.
async function exec(commands, label) {
  var cmds = commands || []
  const cmdList = cmds.map(function(c, i) { return (i + 1) + '. ' + selfContained(c) }).join('\n')
  const prompt =
    'Run each of the following commands in order using the Bash tool. ' +
    'Return ONLY a raw JSON array and NOTHING else — no prose, no explanation, no markdown fences; ' +
    'your entire response must be valid for JSON.parse. ' +
    'Each element: {"index":<0-based>,"ok":<true|false>,"stdout":<string>}. ' +
    'The "stdout" value MUST be the command\'s COMPLETE raw stdout, copied verbatim as a single JSON ' +
    'string (JSON-escape quotes/newlines as needed). Do NOT parse it, extract a field from it, summarize ' +
    'it, pretty-print it, or change it in any way — even when the stdout is itself a JSON object, return ' +
    'that object byte-for-byte as the string value, never a parsed/abbreviated version of it.\n\n' +
    cmdList
  const o = { model: cheapestModel(), label: label || 'exec', courier: true }
  const out = await globalThis.agent(prompt, o)
  return _parseExecResult(out, cmds.length)
}

// execJson/execText: run ONE command via the courier dumb-pipe (pinned to the cheapest model by the
// bundle preamble via the `courier: true` marker) and parse its stdout. Mirrors build_phase.js's
// helpers: the courier retries ONCE on a dropped/garbled stdout (FR-8), returns null after the retry
// so the caller fails closed, and returns a parseable {"ok":false} (a REAL failure) as-is without
// retry. `label` is the cosmetic display purpose (defaults to 'exec'); routing rides `courier: true`.
async function execJson(cmd, label) {
  try {
    return await courier.runCourierJson(label || 'exec', cmd)
  } catch (e) {
    if (e instanceof courier.CourierTransportError) return null
    throw e
  }
}
async function execText(cmd, label) {
  try {
    return (await courier.runCourierText(label || 'exec', cmd)).trim()
  } catch (e) {
    if (e instanceof courier.CourierTransportError) return null
    throw e
  }
}

// persistPhase: one 'save phase progress' courier — the optional side-effect command chained (&&)
// before phase_progress_entry.py save, which writes journal + checkpoint and read-back-confirms both.
// Persist order (FR-4): side-effect first (when present), then journal, then checkpoint (cursor last).
// Every interpolated non-constant arg is shq()-quoted.
// opts.journalOnly (#118 "save phase progress" on a PARK): record the journal entry (+ chained
// side-effect) durably but leave the checkpoint cursor untouched — a parked phase did not complete,
// so advancing lastGoodStep would make the resume skip it. Still ONE courier leaf.
// Returns {ok: boolean} — ok is false if any command in the batch reported failure.
async function persistPhase(workItem, opts) {
  opts = opts || {}
  const sideEffectCmd = opts.sideEffectCmd || null
  const record = opts.record || opts.journalPayload || {}
  const step = opts.step
  const phase = opts.phase
  const journalOnly = !!opts.journalOnly
  const side = journalOnly ? null : (opts.sideEffect || null)
  const sideArg = side ? ` --json ${shq(JSON.stringify(side))}` : ''
  const joArg = journalOnly ? ' --journal-only' : ''
  // #130: fold this phase's cost telemetry into the SAME durable write (no new leaf — #118). The
  // phase_cost event is written best-effort inside phase_progress_entry.py, only when the phase
  // record is freshly applied (so a resume never double-counts). Absent when there's nothing to
  // record (no dispatches, unmeasured) or when the caller did not opt in (recordCost).
  const costBody = opts.recordCost ? phaseCostPayload(phase) : null
  const costArg = costBody ? ` --cost-payload ${shq(JSON.stringify(costBody))}` : ''
  // #130: on a park (journalOnly), fold a `parked` terminal marker into this same save so the run is
  // classifiable as parked (parkFromPhases journals nothing) — carrying its already-folded cost.
  const parkArg = (journalOnly && opts.parkReason) ? ` --terminal-park ${shq(String(opts.parkReason))}` : ''
  const saveCmd =
    `python3 ${libPath('phase_progress_entry.py')} save --work-item ${shq(workItem)} ` +
    `--step ${shq(String(step))} --phase ${shq(phase)} --payload ${shq(JSON.stringify(record))}${sideArg}${joArg}${costArg}${parkArg}`
  const cmd = sideEffectCmd ? `${sideEffectCmd} && ${saveCmd}` : saveCmd
  // #170: the SECOND (and last) libRoot probe site — the once-per-phase durable write covers the long
  // back half, where a plugin-cache eviction after startup would otherwise surface as a raw python
  // file-not-found. In dev/dogfood (relative libRoot) libRootProbe() is empty, so this is byte-identical.
  const probedCmd = `${libRootProbe()}${cmd}`
  const required = journalOnly
    ? ['ok', 'journal_confirmed']
    : ['ok', 'journal_confirmed', 'checkpoint_confirmed']
  try {
    const res = await courier.runCourierMarkedJson(
      'save phase progress',
      probedCmd,
      { require: required, retryRealFailure: false },
    )
    // Map the libRoot-missing marker to the SAME named park reason reconcile uses, before the
    // save-result read-back check — the back half fails closed with a descriptive cause, not a
    // generic read-back mismatch.
    if (res && typeof res.reason === 'string' && res.reason.indexOf(MISSING_MARKER) >= 0) {
      return { ok: false, error: 'spine code root missing (libRoot)' }
    }
    const confirmed = res && res.ok && res.journal_confirmed &&
      (journalOnly || res.checkpoint_confirmed)
    return confirmed
      ? { ok: true, recovered: false }
      : { ok: false, error: (res && res.reason) || 'phase progress read-back mismatch' }
  } catch (e) {
    if (e instanceof courier.CourierTransportError) {
      return { ok: false, error: 'phase progress save transport failed (courier): ' + e.reason }
    }
    return { ok: false, error: 'phase progress save transport failed (courier)' }
  }
}

// #130: the phase_cost payload for a completed phase — the proxy dispatch counts (× resolved model)
// + the budget-derived output-token delta. Folded into the phase's ONE durable write (the save leaf
// for a normal phase, the readout_post hand-back for ship) so it rides no new courier leaf (#118).
// Returns null when there is nothing worth recording (no dispatches, unmeasured).
function phaseCostPayload(phase) {
  try {
    const body = costMeter.take(phase)
    return costMeter.isEmpty(body) ? null : body
  } catch (_e) { return null }
}

function inWorktree(cmd, worktree) {
  return worktree ? `cd ${shq(worktree)} && ${cmd}` : cmd
}
function targetCommandPrompt(prompt, worktree) {
  if (!worktree || typeof prompt !== 'string') return prompt
  if (!prompt.startsWith('Run exactly this')) return prompt
  // The courier shape is "Run exactly this …:\n\n<cmd>"; split on the FIRST blank-line boundary
  // so a multi-line command (which may itself contain a blank line) is wrapped whole, not just its tail.
  const idx = prompt.indexOf('\n\n')
  if (idx < 0) return prompt
  const prefix = prompt.slice(0, idx + 2)
  const cmd = prompt.slice(idx + 2)
  if (!cmd.trim() || cmd.trim().startsWith('cd ')) return prompt
  return `${prefix}${inWorktree(cmd, worktree)}`
}
async function withTargetCommandPrompts(worktree, fn) {
  if (!worktree) return fn()
  const originalAgent = globalThis.agent
  globalThis.agent = async (prompt, opts) => originalAgent(targetCommandPrompt(prompt, worktree), opts)
  try {
    return await fn()
  } finally {
    globalThis.agent = originalAgent
  }
}

// JS<->Python bridge: run a lib command in a leaf, return its stdout JSON (schema-validated).
// #118 residual: ONLY the test-pilot per-op leaves (testPilotDeps' cli/jsonCommand) still ride this
// StructuredOutput pipe — every spine site is ported to courier_exec/exec. It is a dumb pipe, so it
// is pinned to the cheapest model here AND marked courier:true for the bundle preamble's
// unconditional pin (the live 2026-07-02 run showed unmarked cmdRunner leaves inheriting the
// session model at ~41k tokens per command echo).
// FR-5 (cwd-rooting): wrap the command with selfContained() so the courier leaf always runs from
// the repo root when globalThis.__SR_ROOT is set. selfContained is a no-op when __SR_ROOT is unset
// (smoke/test backward-compat) and skips commands already starting with `cd ` (no double-cd).
async function cmdRunner(cmd, { schema, label }) {
  // The command prints ONE JSON object to stdout. The leaf must map each top-level key of that
  // object to the SAME-named StructuredOutput field — NOT stuff the whole JSON text into one field
  // (a live-only derailment: that is schema-valid-but-wrong, e.g. action="{...the whole blob...}",
  // which then mis-routes the deciders). Spell the mapping out so the leaf can't collapse it.
  return agent(
    `Use the Bash tool to run exactly this command. It prints ONE JSON object to stdout. Return that ` +
    `object via StructuredOutput by copying each of its top-level keys to the same-named output field, ` +
    `values exactly as printed. Do NOT put the whole JSON into a single field, do NOT stringify or nest ` +
    `it, and do NOT add commentary or extra fields:\n\n${selfContained(cmd)}`,
    { label: label || 'lib', schema, courier: true, model: cheapestModel() },
  )
}

// Reconcile-from-store: exec gathers the world snapshot via recover_entry.py --snapshot
// (IO: store, enforcer, lease, checkpoint, world read), then the JS twin decides (pure, in-process).
// generation is threaded from the Python snapshot (UFR-10).
async function reconcile(workItem) {
  const preRoot = checkoutRoot()
  const rootFlag = preRoot ? ` --root ${shq(preRoot)}` : ''
  const snapCmd =
    `${libRootProbe()}python3 ${libPath('recover_entry.py')} --work-item ${shq(workItem)} --snapshot${rootFlag}`
  let _snapStdout = ''
  try {
    _snapStdout = await courier.runCourierMarkedText('gather snapshot', snapCmd)
  } catch (_e) {
    return { action: 'park_gate', reason: 'recover_entry snapshot failed (IO error)', generation: null }
  }
  // #170 fail-closed probe: an ABSOLUTE spine code root that vanished mid-run (e.g. plugin-cache
  // eviction) short-circuits the compose to MISSING_MARKER instead of a file-not-found python error —
  // park with a NAMED reason so the readout says exactly what's wrong. Relative (dev) libRoot never
  // emits the marker.
  if (_snapStdout.indexOf(MISSING_MARKER) >= 0) {
    return { action: 'park_gate', reason: 'spine code root missing (libRoot)', generation: null }
  }
  let snap = null
  try { snap = JSON.parse(_snapStdout) } catch (_) {}
  if (!snap) {
    // A failed/empty snapshot (IO error, store unusable before lease) -> fail closed.
    return { action: 'park_gate', reason: 'recover_entry snapshot failed (IO error)', generation: null }
  }
  // recover_entry emits an early_park when the cursor guard triggers (before snapshot).
  // In that case the snapshot fields are absent and {action, reason, generation} come directly.
  if (snap.action) return snap   // early park (cursor_gate or store/enforcer/lease failure)
  if (!snap.root || typeof snap.root !== 'string' || !String(snap.root).trim()) {
    return {
      action: 'park_gate',
      reason: 'recover_entry snapshot missing checkout root',
      generation: snap.generation ?? null,
    }
  }
  if (typeof globalThis !== 'undefined') globalThis.__SR_ROOT = String(snap.root)
  const decision = recoverTwin.reconcile(snap.checkpoint, snap.world)
  return Object.assign({}, decision, { generation: snap.generation, root: snap.root })
}

// releaseLease: CAS-release the work-item ref-lease at EVERY terminal exit of the run — parks
// and hand-backs alike — so a relaunch never waits out DEFAULT_TTL (live 2026-07-02: each park
// cost 30 minutes). Only fires when THIS run acquired (generation threaded from reconcile; a
// lease-held park carries none). Best-effort: a failed release leaves the TTL as the backstop,
// and the generation precondition means a superseded holder's lease is never deleted.
// This is a state-changing single command, so it rides a DEDICATED hardened courier (NOT the
// permissive batch exec): a strict prompt forbidding extra commands + require(['ok']) so a
// freestyling courier's chatty answer is rejected and retried rather than accepted. Live
// 2026-07-02 the park-path release rode the batch exec and the courier improvised ~10 unscripted
// Bash calls, "manually" releasing the lease itself — the misbehaving-courier class #138 hardened
// for WRITES, now closed for this exec leaf too.
async function releaseLease(workItem, generation, root) {
  if (generation == null) return
  const cmd = fenceCliCmd(workItem, generation, root, ' --release')
  if (!cmd) return
  try {
    await courier.runCourierJson(
      'release lease',
      cmd,
      { require: ['ok'], retryRealFailure: false, strict: true },
    )
  } catch (_) { /* TTL backstop */ }
}

// Park from runPhases: persist the journal (caller already did) then release the lease before
// returning — same release-on-park path reconcile/startup use. Belt-and-braces with showrunner()'s
// finally (a second release no-ops when the lease is already gone).
async function parkFromPhases(workItem, generation, root, phase, reason) {
  await releaseLease(workItem, generation, root)
  return { outcome: 'parked', phase, reason }
}

// #25 quick discovery — the showrunner's INTAKE contract. Discovery (the architect session) always
// produces the run's input artifact; the ROUTE decides which one: full = spec (today), quick = the
// tasks doc, built from `workhorse` on (plan/review-plan/tasks/review-tasks skipped). This is the
// spine leg only — PR 2 owns the-architect's route recommendation, quick-mode task authoring, the
// alignment probe, and the gate wiring that launches a quick run.
//
// resolveIntake: PURE decider over the startup facts (spec/tasks presence + gates) and the launch's
// explicit route (globalThis.__SR_ROUTE, threaded from args.route). Returns the route plus, for the
// quick route, either the tasks gate to check or a fail-closed REFUSE — a missing or malformed tasks
// artifact never silently falls back to (or past) the full path. Byte-identical to today on the full
// route: an absent explicit route with no tasks artifact resolves to 'full', so the spec-gate startup
// path is unchanged.
//   facts:    { spec_present, tasks_present, spec_gate, tasks_gate } (from readStartupState)
//   explicit: the launch-declared route ('quick' | 'full' | null)
//   returns:  { route:'full' }
//           | { route:'quick', action:'gate', gate:<tasks_gate> }
//           | { route:<declared|'quick'>, action:'refuse', reason:<why> }
function resolveIntake(facts, explicit) {
  facts = facts || {}
  const specPresent = !!facts.spec_present
  const tasksPresent = !!facts.tasks_present
  // The route the on-disk artifacts SUPPORT: spec present ⇒ full (spec-anchored); else a tasks doc
  // alone ⇒ quick; else neither ⇒ null (no input artifact resolved yet).
  const derived = specPresent ? 'full' : (tasksPresent ? 'quick' : null)
  const declared = (explicit === 'quick' || explicit === 'full') ? explicit : null
  // A DECLARED route that conflicts with what the artifacts support is a fail-closed REFUSE — never
  // silently overridden in EITHER direction. Declared 'quick' over a present spec would run the full
  // route unattended (regenerating tasks.md over the architect's quick doc and building off a
  // maybe-stale spec); declared 'full' over a spec-less tasks doc would skip the exact front half the
  // launch asked for. Both are fail-open against the launch's stated intent — refuse and name what to
  // reconcile, rather than pick a route the owner did not choose.
  if (declared && derived && declared !== derived) {
    const artifact = derived === 'full'
      ? 'a spec is present on disk (the full route)'
      : 'only a tasks doc — no spec — is present on disk (the quick route)'
    return { route: declared, action: 'refuse',
      reason: `launch declared the '${declared}' route but ${artifact} — refusing to launch ` +
        `(fail-closed intake); reconcile the route with the on-disk artifact before relaunching` }
  }
  // No conflict below (the declared route agrees with the artifacts, or nothing was declared).
  // Spec present ⇒ full route (spec-anchored, byte-identical to pre-#25).
  if (specPresent) return { route: 'full' }
  const declaredQuick = explicit === 'quick'
  if (!tasksPresent) {
    // No tasks artifact. A launch that DECLARED quick must refuse (fail-closed intake — never fall
    // back to the full path, and never fall past tasks into an empty build). Otherwise this is the
    // pre-#25 no-spec world: the full route parks at the spec startup gate (unreadable), unchanged.
    if (declaredQuick) {
      return { route: 'quick', action: 'refuse',
        reason: 'quick-route launch declared, but no tasks artifact was found where the tasks phase writes it ' +
          '— refusing to launch (fail-closed intake), never falling back to the full path' }
    }
    return { route: 'full' }
  }
  // Tasks artifact present, no spec ⇒ quick route. Validate it is well-formed BEFORE gating: a doc
  // whose review gate can't be parsed (malformed frontmatter, missing gates line, or unreadable) is
  // a fail-closed refuse — the run never builds off an artifact it can't verify the owner approved.
  const g = facts.tasks_gate
  if (g == null || g === 'malformed' || g === 'unreadable') {
    return { route: 'quick', action: 'refuse',
      reason: 'quick-route tasks artifact is malformed or missing its review gate (' + String(g) + ') ' +
        '— refusing to launch (fail-closed intake)' }
  }
  return { route: 'quick', action: 'gate', gate: g }
}

// #25 quick discovery — record, DURABLY and honestly, the front-half phases the quick route skips so
// they are never silently absent from the run's audit trail (journal) or its live readout (run_watch
// renders the phases_skipped event). A structured, non-secret payload (fixed phase names + route),
// written AS-IS via the generic journal_entry.py seam. Returns false on a failed durable write so the
// caller fails closed — an unrecorded skip must not proceed (the run's durable-write discipline).
async function recordSkippedPhases(workItem, skipped, entryPhase) {
  const payload = { route: 'quick', skipped: skipped || [], entryPhase: entryPhase || 'workhorse' }
  const out = await execJson(
    `python3 ${libPath('journal_entry.py')} --work-item ${shq(workItem)} ` +
    `--event-type phases_skipped --payload ${shq(JSON.stringify(payload))}`,
    'record skipped phases')
  return !!(out && out.ok)
}

async function showrunner({ workItem }) {
  // Progress-group the pre-loop leaves (reconcile / spec-gate / startup) under 'startup'; runPhases
  // re-stamps this per phase. Read by the bundle's agent wrapper (globalThis.__SR_PHASE).
  if (typeof globalThis !== 'undefined') globalThis.__SR_PHASE = 'startup'
  const r = await reconcile(workItem)
  if (r.action === 'park_gate' || r.action === 'gate') {
    await releaseLease(workItem, r.generation, r.root)
    return { outcome: 'parked', phase: 'reconcile', reason: r.reason || r.action }
  }
  // UFR-1 / #25 intake: refuse to run unless the route's input artifact is approved. resolveIntake
  // (pure) picks the route from the durable artifact state (spec present ⇒ full, else tasks ⇒ quick)
  // and the launch-declared route; on the quick route it either hands back the tasks gate to check or
  // fail-closes (missing/malformed tasks artifact ⇒ refuse, never a silent fall-back to/past full).
  const startupFacts = await readStartupState(workItem)
  const _explicitRoute = (typeof globalThis !== 'undefined' && globalThis.__SR_ROUTE) || null
  const intake = resolveIntake(startupFacts || {}, _explicitRoute)
  const route = intake.route
  // A fail-closed refuse parks regardless of which route it carries — a declared-vs-artifact conflict
  // refuses under the DECLARED route (which may be 'full'), so this is not gated on route === 'quick'.
  if (intake.action === 'refuse') {
    await releaseLease(workItem, r.generation, r.root)
    return { outcome: 'parked', phase: 'startup', reason: intake.reason }
  }
  // Full route ⇒ the spec gate (byte-identical to pre-#25); quick route ⇒ the owner-approved tasks
  // gate. The startup decider (phase_step) proceeds only on a `passed` gate; anything else parks.
  const startupGate = route === 'quick' ? intake.gate : ((startupFacts && startupFacts.spec_gate) || 'unreadable')
  const startup = await phaseStep({ confidence: 'high', assumptions: [] }, startupGate)
  if (startup.action !== 'proceed') {
    await releaseLease(workItem, r.generation, r.root)
    return { outcome: 'parked', phase: 'startup', reason: startup.reason }
  }
  const _ovMap = (startupFacts && startupFacts.model_overrides) || {}
  if (typeof globalThis !== 'undefined') {
    globalThis.__SR_OVERRIDES = (_ovMap && typeof _ovMap === 'object' && !Array.isArray(_ovMap)) ? _ovMap : {}
  }
  // Plant the startup-resolved, storage-mode-aware docs dir for docDirFor (docPathFor /
  // notifyLedgerFor). Best-effort: an absent/empty doc_dir (resolution failed, or an older canned
  // response) plants nothing and the legacy in-repo fallback stays in force.
  const _docDir = (startupFacts && typeof startupFacts.doc_dir === 'string' && startupFacts.doc_dir) || null
  if (_docDir && typeof globalThis !== 'undefined') {
    globalThis.__SR_DOC_DIRS = Object.assign({}, globalThis.__SR_DOC_DIRS, { [workItem]: _docDir })
  }
  // #38 engine preferences, #118 startup fold: the per-role engine prefs ride the SAME
  // 'read startup state' gather (previously a third startup courier leaf, engine_pref_load.py —
  // the one the #118 matrix does not allow: startup is the deliberately-TWO-leaf stretch).
  // Fail-safe: an absent/malformed (or courier-stringified) value yields both-"claude" + empty
  // effort map, so the review/build leaves take the byte-unchanged agent() path.
  const _epParsed = _coerceObj((startupFacts && startupFacts.engine_prefs) || null)
  let _epMap = { reviewer: 'claude', implementation: 'claude', planAuthor: 'claude', effort: {} }
  if (_epParsed && typeof _epParsed === 'object' && !Array.isArray(_epParsed)) {
    // Carry the whole object — reviewer/implementation/planAuthor AND the FR-9 effort sub-map
    // (keyed by role_kind), so resolveEffort can source the owner's effort override from
    // __SR_ENGINE_PREFS.effort (NOT from the model-tier __SR_OVERRIDES map, which is keyed by
    // role->model).
    _epMap = {
      reviewer: _epParsed.reviewer || 'claude',
      implementation: _epParsed.implementation || 'claude',
      planAuthor: _epParsed.planAuthor || 'claude',
      effort: (_epParsed.effort && typeof _epParsed.effort === 'object' && !Array.isArray(_epParsed.effort)) ? _epParsed.effort : {},
    }
  }
  if (typeof globalThis !== 'undefined') globalThis.__SR_ENGINE_PREFS = _epMap
  // 'continue' (from_step) or 'world_derive' (from_step 0) -> run the phase loop (Task 8).
  // lastGoodStep = the last *completed* phase index; resume at the next one (no re-run, FR-3).
  // #25: a FRESH quick run starts at `workhorse` (plan/review-plan/tasks/review-tasks skipped — the
  // tasks doc IS the input artifact). A resume rides the durable cursor unchanged (it already points
  // past the skipped phases, so route need not survive resume for the cursor); the full route's fresh
  // start stays 0 (byte-identical).
  const _resuming = r.action === 'continue' && r.from_step != null
  const _workhorseStep = PHASES.indexOf('workhorse')
  const fromStep = _resuming
    ? Number(r.from_step) + 1
    : (route === 'quick' ? _workhorseStep : 0)
  // UFR-10 (#107): thread the lease generation recover_entry acquired into the workhorse build phase,
  // so the build can fence (renew-then-fence) at every branch-mutating boundary.
  const deps = { gateRead: gateReadFor(workItem), generation: r.generation, root: r.root }
  // FR-7 (#108)/FR-4 (#102)/Task-13a (#115): native front-half wiring. Three opt-in selectors
  // share the native authoring deps but differ on the boundary park:
  //   - env SUPERHEROES_FRONT_HALF=native: direct-node/smoke path (procEnv); keeps boundary park.
  //   - globalThis.SUPERHEROES_FRONT_HALF_NATIVE: Workflow-sandbox path (set by the ENTRY from
  //     args.frontHalf==='native'); procEnv is unavailable in the sandbox (FR-8), so the ENTRY
  //     injects this globalThis flag instead.
  //   - SUPERHEROES_BUNDLE_FULL_RUN true (preamble default + full-run ENTRY): no boundary park,
  //     proceeds into the back-half.
  // #25: the quick route skips the whole front half (fromStep starts at `workhorse`), so the native
  // authoring/boundary deps are irrelevant — and the boundary MUST NOT be wired, or it would fire at
  // `workhorse` and park a quick run immediately. The full route wires them exactly as pre-#25.
  const fullRun = !!globalThis.SUPERHEROES_BUNDLE_FULL_RUN
  const frontHalfNative = procEnv('SUPERHEROES_FRONT_HALF') === 'native' || !!globalThis.SUPERHEROES_FRONT_HALF_NATIVE
  if (route !== 'quick' && (frontHalfNative || fullRun)) {
    deps.produce = producePhase                  // plan / tasks authoring (author-only)
    deps.reviewDoc = reviewDocPhase              // review-plan / review-tasks -> panel-doc leg
    if (!fullRun) deps.frontHalfBoundary = frontHalfBoundary   // front-half-only keeps the boundary park
  }
  // #25: on a FRESH quick entry, durably record the skipped front-half phases before entering the
  // loop — honest in the journal + readout, never silently absent. A failed durable write fails
  // closed (park at startup) rather than proceed on an unrecorded skip (the run's durable-write
  // discipline). A resume WITH a cursor does not re-record; a relaunch that re-enters the build from
  // scratch (parked before its first checkpoint, so no cursor) re-asserts the skip — honest and
  // harmless (no consumer counts these; run_readout reads the route from state, not the event tally).
  if (route === 'quick' && !_resuming) {
    const recorded = await recordSkippedPhases(workItem, PHASES.slice(0, _workhorseStep), 'workhorse')
    if (!recorded) {
      await releaseLease(workItem, r.generation, r.root)
      return { outcome: 'parked', phase: 'startup',
        reason: 'quick-route skipped-phase record could not be written durably — refusing to launch on an unrecorded skip' }
    }
  }
  try {
    return await runPhases(workItem, fromStep, deps)
  } finally {
    // Every runPhases exit is terminal for THIS run — phaseStep park, boundary park, or the
    // ship hand-back ('ready') — and a crash unwinds through here too. Release the lease so
    // the relaunch (or the owner's next run) never waits out the TTL.
    await releaseLease(workItem, r.generation, r.root)
  }
}

// readGate: IO read via exec (definition-doc on disk). A missing/malformed doc returns the
// 'unreadable' sentinel that phaseStep twin maps to park_unexpected_gate.
async function readGate(workItem, doc) {
  try {
    const results = await exec([
      `python3 ${libPath('definition_doc.py')} read-gate --doc ${shq(doc)} ` +
      `--work-item ${shq(workItem)} --root "$(git rev-parse --show-toplevel)" --json`,
    ], 'read gate')
    let out = null
    try { out = JSON.parse((results[0] && results[0].stdout) || '') } catch (_) {}
    return (out && out.review) || 'unreadable'
  } catch (_) {
    return 'unreadable'
  }
}

// #221: the startup-state gather script, extracted so a Node smoke can run the REAL Python against an
// out-of-repo fixture (the canned-answer smokes were blind to the actual engine-prefs resolution —
// exactly how the load_engine_prefs store-base bug shipped). pyLibDir() is read at CALL time, so a
// smoke can point sys.path at the real lib dir by planting an absolute __SR_LIB before calling this.
function startupStateScript() {
  return [
    'import json, os, sys',
    `sys.path.insert(0, ${pyLibDir()})`,
    'import definition_doc, model_tier_overrides',
    'wi = sys.argv[1]',
    'root = sys.argv[2]',
    'spec_gate = "unreadable"',
    'doc_dir = ""',
    // #25 intake facts: which input artifact discovery produced decides the route (spec ⇒ full,
    // tasks ⇒ quick). Read presence + gate for BOTH from the SAME mode-aware, spec-anchored resolver
    // the tasks phase writes through, so the showrunner reads exactly the doc a quick run built off.
    'spec_present = False',
    'tasks_present = False',
    'tasks_gate = None',
    'try:',
    '    d = definition_doc.resolve_work_item_dir(wi, root=root, cwd=root)',
    '    doc_dir = d',   // the storage-mode-aware docs dir — planted on __SR_DOC_DIRS (docDirFor)
    '    spec_present = os.path.isfile(os.path.join(d, "spec.md"))',
    '    tasks_present = os.path.isfile(os.path.join(d, "tasks.md"))',
    '    if spec_present:',
    '        try:',
    '            spec_gate = definition_doc.read_gate(os.path.join(d, "spec.md"))',
    '        except Exception:',   // present but unparseable — same "unreadable" the full path saw pre-#25
    '            spec_gate = "unreadable"',
    '    if tasks_present:',
    '        try:',
    '            tasks_gate = definition_doc.read_gate(os.path.join(d, "tasks.md"))',
    '        except Exception:',   // present but its review gate can't be parsed — fail-closed marker
    '            tasks_gate = "malformed"',
    'except Exception:',
    '    pass',
    'try:',
    '    overrides = model_tier_overrides.load_overrides(None) or {}',
    'except Exception:',
    '    overrides = {}',
    'if not isinstance(overrides, dict):',
    '    overrides = {}',
    // #118 startup fold: the engine-prefs read (previously its own engine_pref_load.py exec leaf,
    // the third startup courier) rides the same gather. Fail-open like engine_pref_load.py: ANY
    // failure yields the degenerate both-'claude' map.
    '_ep_degenerate = {"reviewer": "claude", "implementation": "claude", "effort": {}}',
    'try:',
    '    import engine_pref',
    // #221: the SECOND arg is the store-base override (the ~/.claude/superheroes test seam), NOT the
    // repo root. `root` here IS the repo root — passing it resolves core.md to a nonexistent
    // <repo>/projects/<key>/config/core.md, so the deliberate fail-open silently degraded every run
    // to all-claude. Pass None so core.md resolves at the real store; the repo root rides `cwd` (arg 1).
    '    engine_prefs = engine_pref.load_engine_prefs(root, None)',
    '    if not isinstance(engine_prefs, dict):',
    '        engine_prefs = _ep_degenerate',
    'except Exception:',
    '    engine_prefs = _ep_degenerate',
    'print(json.dumps({"ok": True, "spec_gate": spec_gate, "model_overrides": overrides, "doc_dir": doc_dir, "engine_prefs": engine_prefs, "spec_present": spec_present, "tasks_present": tasks_present, "tasks_gate": tasks_gate}))',
  ].join('\n')
}

async function readStartupState(workItem) {
  const script = startupStateScript()
  try {
    return await courier.runCourierJson(
      'read startup state',
      `python3 -c ${shq(script)} ${shq(workItem)} "$(git rev-parse --show-toplevel)"`,
      // doc_dir is REQUIRED: the Python side always emits it (empty string on a failed
      // resolution), so an absent field means a mangled courier response — retry rather than
      // silently planting nothing (which would mis-route the NOTIFY ledger + review doc paths
      // to the in-repo fallback on an out-of-repo-calibrated project mid-run).
      // engine_prefs is NOT required: an older canned response without it degrades to the safe
      // both-'claude' default (the same fail-open engine_pref_load.py had), never a retry.
      { require: ['ok', 'spec_gate', 'model_overrides', 'doc_dir'] },
    )
  } catch (_) {
    return { ok: true, spec_gate: 'unreadable', model_overrides: {}, doc_dir: '', engine_prefs: null }
  }
}

async function readDefinitionDraft(workItem, doc) {
  const label = doc === 'plan' ? 'read plan draft' : 'read tasks draft'
  const script = [
    'import json, os, sys',
    `sys.path.insert(0, ${pyLibDir()})`,
    'import definition_doc',
    'wi = sys.argv[1]',
    'doc = sys.argv[2]',
    'root = sys.argv[3]',
    'd = definition_doc.resolve_work_item_dir(wi, root=root, cwd=root)',
    'p = os.path.join(d, f"{doc}.md")',
    'exists = os.path.isfile(p)',
    'gate = definition_doc.read_gate(p) if exists else "unreadable"',
    'print(json.dumps({"ok": True, "path": p, "docType": doc, "gate": gate, "exists": exists}))',
  ].join('\n')
  return courier.runCourierJson(
    label,
    `python3 -c ${shq(script)} ${shq(workItem)} ${shq(doc)} "$(git rev-parse --show-toplevel)"`,
    { require: ['ok', 'path', 'docType'] },
  )
}

const REVIEWED = new Set(['review-plan', 'review-tasks', 'review-code'])
function gateReadFor(workItem) {
  return async (phase) => {
    if (!REVIEWED.has(phase)) return null            // authoring phase: no review gate
    if (phase === 'review-code') return null          // review-code's gate = the reviewPanel verdict (Task 10)
    const doc = phase === 'review-plan' ? 'plan' : 'tasks'
    return readGate(workItem, doc)
  }
}

const PHASES = ['plan', 'review-plan', 'tasks', 'review-tasks', 'workhorse',
                'review-code', 'draft-PR', 'test-pilot', 'mark-ready', 'ship']

// phaseStep: pure in-process JS twin (phase_step.decide). No agent dispatch.
function phaseStep(phaseResult, gate) {
  return phaseStepTwin.decide(phaseResult, gate)
}

async function defaultTestPilotPhase(workItem, generation) {
  return testPilotPhase(workItem, generation, testPilotDeps(workItem, generation))
}

// Boundary coercion: parse a value the courier may have stringified (#115 "parse facts at boundary").
// Applies to known nested-object fields in the resolveContext result. If the value is a string that
// JSON-parses to a dict, array, or null, return the parsed result. Otherwise return the value unchanged
// so downstream consumers (writeJson, _is_object guards) still fail-closed on non-parseable strings.
// Arrays are included because allowedOrigins is a JSON array (e.g. '["http://localhost:3000"]') and
// must coerce back to an array; a non-container parse result (number, bool) stays as the original string.
const _coerceObj = (v) => {
  if (typeof v !== 'string') return v
  try {
    const p = JSON.parse(v)
    if (p === null || (typeof p === 'object')) return p
  } catch (_) { /* fall through */ }
  return v
}

function testPilotDeps(workItem, generation) {
  const runDir = joinPath(io().tmpdir(), `showrunner-${workItem}-test-pilot`)
  // writeJson is async (the io() seam is async — see io_seam.js) and lazily ensures runDir, so every
  // call site must await it. Lazy mkdirp keeps the dir-create on the same awaited path as the write.
  const writeJson = async (name, value) => {
    const p = joinPath(runDir, `${name}.json`)
    await io().mkdirp(runDir)
    await io().writeFile(p, JSON.stringify(value || {}))
    return p
  }
  const jsonCommand = (cmd, schema) => cmdRunner(cmd, { schema: schema || { type: 'object' } })
  const cli = (cmd, schema) => jsonCommand(cmd, schema || { type: 'object' })
  const keyFor = (branch) => encodeURIComponent(branch || workItem).replace(/~/g, '%7E')

  return {
    resolveContext: async () => {
      // FIX B: resolve build worktree (same way review-code does) + thread configurable base.
      // resolveBuildTarget is defined later in this file but testPilotDeps is called after module
      // load, so the forward reference resolves correctly at call time.
      // Fail-closed: an unresolvable build worktree must PARK, never silently run the context CLI
      // against the showrunner's OWN tree. Without --worktree, test_pilot_context_cli falls back to
      // the showrunner checkout, whose diff misclassifies applicability (typically 'not_applicable')
      // and SKIPS test-pilot with no park/log — a silent fail-open. Throwing here is caught by
      // resolveApplicabilityAndSetup -> a low-confidence park (mirrors reviewCodePhase's null-resolver
      // park; honors the profile invariant "unresolvable -> fail-closed PARK, never act on the wrong tree").
      const target = await resolveBuildTarget(workItem).catch(() => null)
      if (!target || !target.worktree) {
        throw new Error('could not resolve the build worktree for test-pilot — refusing to run against the showrunner tree')
      }
      const wtArg = ` --worktree ${shq(target.worktree)}`
      // FR-8: mirror the __SR_BASE pattern from shipPhase / draftPRPhase.
      const _srBase = (typeof globalThis !== 'undefined' && globalThis.__SR_BASE) ? String(globalThis.__SR_BASE) : null
      const baseArg = _srBase ? ` --base ${shq(_srBase)}` : ''
      const raw = await courier.runCourierJson(
        'read test context',
        `python3 ${libPath('test_pilot_context_cli.py')} resolve ` +
        `--work-item ${shq(workItem)}${generation != null ? ` --generation ${shq(String(generation))}` : ''}` +
        `${wtArg}${baseArg}`,
        { require: ['head'] },
      )
      // FIX A: coerce nested fields the cheap courier may have stringified (same class as verify_gate).
      // Strings, head, branch, workItem stay as-is; only known object/null fields are coerced.
      if (raw && typeof raw === 'object') {
        for (const field of ['diff', 'detectors', 'profile', 'pr', 'browserTool', 'allowedOrigins', 'store']) {
          if (field in raw) raw[field] = _coerceObj(raw[field])
        }
      }
      return raw
    },

    derivePlan: async (context) => agent(
      `You are the test-pilot plan leaf for work-item ${workItem}. Derive a browser test plan for ` +
      `the current branch head ${context.head}. Return ONLY JSON ` +
      `{"records":[{"branch":${JSON.stringify(context.branch)},"steps":[{"id","instruction","expected","scenarioIds":[]}]}],` +
      `"coverageRationale":"..."}. Use concise stable step ids; include scenarioIds when seed scenarios are needed.`,
      { label: 'plan-tests', schema: { type: 'object', required: ['records'], properties: { records: { type: 'array' } } } }),

    preparePlanRecords: async (plan) => ({ action: 'ready', records: plan.records || [] }),

    prepareTestRun: async ({ plan, records, context }) => {
      const pr = context.pr && context.pr.number
      if (!pr) return { action: 'park', reason: 'test-pilot artifacts require a draft PR number' }
      const planPath = await writeJson('plan-artifact', { key: keyFor(context.branch), records })
      const resultsPath = await writeJson('results-artifact-initial', { key: keyFor(context.branch), records: [], coverageRationale: plan.coverageRationale })
      const profilePath = await writeJson('server-profile', context.profile || {})
      const detectionPath = await writeJson('server-detection', context.detectors || {})
      const recordsPath = await writeJson('seed-records', records)
      const manifestPath = await writeJson('prepare-run-manifest', {
        artifacts: [
          'python3', libPath('test_pilot_artifacts_cli.py'), 'ensure',
          '--plan-json', planPath, '--results-json', resultsPath, '--pr', String(pr),
          '--key', keyFor(context.branch),
        ],
        server: [
          'python3', libPath('test_pilot_server_config_cli.py'), 'resolve',
          '--profile-json', profilePath, '--detection-json', detectionPath,
          '--work-item', workItem,
        ],
        seed: [
          'python3', libPath('test_pilot_seed_cli.py'), 'prepare',
          '--records-json', recordsPath,
        ],
      })
      const script = [
        'import json, subprocess, sys',
        'manifest = json.load(open(sys.argv[1], encoding="utf-8"))',
        'def run(argv):',
        '    try:',
        '        proc = subprocess.run(argv, capture_output=True, text=True, timeout=60)',
        '    except subprocess.TimeoutExpired:',
        '        raise RuntimeError("command timed out")',
        '    if proc.returncode != 0:',
        '        raise RuntimeError(proc.stderr or proc.stdout or "command failed")',
        '    return json.loads(proc.stdout or "{}")',
        'try:',
        '    artifactResult = run(manifest["artifacts"])',
        '    serverContext = run(manifest["server"])',
        '    seedResult = run(manifest["seed"])',
        '    print(json.dumps({"ok": True, "artifactResult": artifactResult, "serverContext": serverContext, "seedResult": seedResult}))',
        'except Exception as exc:',
        '    print(json.dumps({"ok": False, "reason": str(exc)}))',
      ].join('\n')
      const out = await courier.runCourierJson(
        'prepare test run',
        `python3 -c ${shq(script)} ${shq(manifestPath)}`,
        { require: ['ok', 'artifactResult', 'serverContext', 'seedResult'], retryRealFailure: false },
      )
      if (!out || !out.ok) return { action: 'park', reason: (out && out.reason) || 'test-pilot preparation failed' }
      return out
    },

    prepareArtifacts: async ({ plan, records, context }) => {
      const pr = context.pr && context.pr.number
      if (!pr) return { action: 'park', reason: 'test-pilot artifacts require a draft PR number' }
      const planPath = await writeJson('plan-artifact', { key: keyFor(context.branch), records })
      const resultsPath = await writeJson('results-artifact-initial', { key: keyFor(context.branch), records: [], coverageRationale: plan.coverageRationale })
      return cli(
        `python3 ${libPath('test_pilot_artifacts_cli.py')} ensure ` +
        `--plan-json ${shq(planPath)} --results-json ${shq(resultsPath)} --pr ${shq(String(pr))} --key ${shq(keyFor(context.branch))}`,
        { type: 'object' })
    },

    resolveServer: async (context) => {
      const profile = await writeJson('server-profile', context.profile || {})
      const detection = await writeJson('server-detection', context.detectors || {})
      return cli(
        `python3 ${libPath('test_pilot_server_config_cli.py')} resolve ` +
        `--profile-json ${shq(profile)} --detection-json ${shq(detection)} --work-item ${shq(workItem)}`,
        { type: 'object' })
    },

    withManagedServer: async (serverContext, run) => {
      const launchPath = await writeJson('server-launch-context', serverContext)
      const launched = await cli(
        `python3 ${libPath('test_pilot_server_config_cli.py')} launch ` +
        `--context-json ${shq(launchPath)}`,
        { type: 'object' })
      if (!launched || launched.verdict === 'park' || launched.action === 'park' || launched.ok === false) {
        return launched
      }
      try {
        const outcome = await run(launched)
        const contextPath = await writeJson('server-finish-context', launched)
        const outcomePath = await writeJson('server-finish-outcome', outcome || {})
        return cli(
          `python3 ${libPath('test_pilot_server_config_cli.py')} finish ` +
          `--context-json ${shq(contextPath)} --outcome-json ${shq(outcomePath)}`,
          { type: 'object' })
      } catch (err) {
        const contextPath = await writeJson('server-finish-context', launched)
        const outcomePath = await writeJson('server-finish-outcome', { action: 'exception', reason: err && err.message ? err.message : String(err) })
        await cli(
          `python3 ${libPath('test_pilot_server_config_cli.py')} finish ` +
          `--context-json ${shq(contextPath)} --outcome-json ${shq(outcomePath)}`,
          { type: 'object' })
        throw err
      }
    },

    seedRecords: async (records) => {
      const recordsPath = await writeJson('seed-records', records)
      return cli(
        `python3 ${libPath('test_pilot_seed_cli.py')} prepare --records-json ${shq(recordsPath)}`,
        { type: 'object' })
    },

    runBrowserPass: async (browserContext) => agent(
      `Run the test-pilot browser pass for work-item ${workItem}. Stay within baseUrl/allowedOrigins and return ONLY JSON ` +
      `{"source":"browser","baseUrl":${JSON.stringify(browserContext.baseUrl)},"steps":[{"id","status","notes","browserExecuted":true,"failureType"?,"summary"?}]}. ` +
      `Browser context: ${JSON.stringify(browserContext)}`,
      { label: 'browser-pass', schema: { type: 'object' } }),

    dispatchFixBatch: async (failures, details) => agent(
      `Fix the app bugs found by native test-pilot for work-item ${workItem}. Commit fixes locally. ` +
      `Return ONLY JSON {"ok":true,"commitShas":["..."],"changedFiles":["..."],"head":"..."}. ` +
      `Failures: ${JSON.stringify(failures)} Details: ${JSON.stringify(details)}`,
      { label: 'fix-app-bug', schema: { type: 'object' } }),

    reviewCode: (wi, opts) => reviewCodePhase(wi, Object.assign({}, opts, {
      runDir: opts.runDir || `/tmp/showrunner-${wi}-review-code-${safeRunKey(opts.runDirSuffix || `${opts.cycle || 1}-${opts.expectedHead || 'head'}`)}`,
    })),

    restoreBaseline: async (records, details) => {
      const recordsPath = await writeJson('restore-records', records)
      const out = await cli(
        `python3 ${libPath('test_pilot_seed_cli.py')} restore-baseline --records-json ${shq(recordsPath)}`,
        { type: 'object' })
      if (out.action === 'park' || out.ok === false) return out
      return Object.assign({}, out, { baseline: { head: details.head, restored: true, status: out.status } })
    },

    ensureFinalArtifacts: async (payload) => {
      const pr = payload.context.pr && payload.context.pr.number
      if (!pr) return { action: 'park', reason: 'final results artifact requires a PR number' }
      const planPath = await writeJson('final-plan-artifact', { key: keyFor(payload.context.branch), records: payload.records })
      const resultsPath = await writeJson('final-results-artifact', Object.assign({ key: keyFor(payload.context.branch) }, payload.aggregated || {}))
      return cli(
        `python3 ${libPath('test_pilot_artifacts_cli.py')} ensure ` +
        `--plan-json ${shq(planPath)} --results-json ${shq(resultsPath)} --pr ${shq(String(pr))} --key ${shq(keyFor(payload.context.branch))}`,
        { type: 'object' })
    },

    publishReady: async (_wi, head, payload) => {
      const statusPath = await writeJson('publish-status', {
        branch: payload.context.branch,
        store: payload.context.store,
        generation,
      })
      const storeArg = payload.context.store ? ` --store ${shq(payload.context.store)}` : ''
      const generationArg = generation ? ` --generation ${shq(String(generation))}` : ''
      return courier.runCourierJson(
        'publish tested head',
        `python3 ${libPath('test_pilot_publish_cli.py')} publish --work-item ${shq(workItem)} ` +
        `--head ${shq(head)} --status-json ${shq(statusPath)} --expected-branch ${shq(payload.context.branch)} ` +
        `${storeArg}${generationArg}`,
        { require: ['ok', 'read_back'], retryRealFailure: false },
      )
    },

    writeStatus: async (status) => {
      if (status.milestone) {
        await writeJson(`milestone-${status.milestone}`, status)
        return { ok: true, read_back: true }
      }
      const statusPath = await writeJson('status-write', status)
      return courier.runCourierJson(
        'write test status',
        `python3 ${libPath('test_pilot_status_cli.py')} write --work-item ${shq(workItem)} --status-json ${shq(statusPath)}`,
        { require: ['ok', 'read_back'], retryRealFailure: false },
      )
    },
  }
}

async function runPhases(workItem, fromStep, deps) {
  deps = deps || {}
  for (let i = fromStep; i < PHASES.length; i += 1) {
    const phase = PHASES[i]
    // Progress-group every leaf dispatched during this phase under the phase name (read by the
    // bundle's agent wrapper). Purely cosmetic — no control-flow effect.
    if (typeof globalThis !== 'undefined') globalThis.__SR_PHASE = phase
    // #130: baseline the output-token cursor at the phase boundary; the phase's cost payload
    // (folded into its persist / hand-back write) diffs the budget delta against this mark.
    costMeter.mark(phase)
    // FR-7: the native front-half ends at its boundary — park before entering the back-half
    // (the 'workhorse' build phase, renamed from 'build' in #107), on a FRESH run AND on a RESUME
    // (a resume re-enters at the build cursor, so the boundary must be checked at that phase, not
    // merely after review-tasks).
    if (deps.frontHalfBoundary && phase === 'workhorse') {
      return deps.frontHalfBoundary(workItem)
    }
    if (phase === 'ship') {                              // terminal: returns {outcome,phase,reason}
      // #130: ship's cost + terminal marker fold into its hand-back readout_post leaf (park() /
      // shipHandback take('ship') and pass --cost-payload + --terminal), so ship rides no new leaf.
      return (deps.ship || shipPhase)(workItem, await loadPr(workItem), deps.generation)
    }
    let phaseResult, gate, sideEffect = null, persist = null
    if (phase === 'review-code') {
      const r = await (deps.reviewCode || reviewCodePhase)(workItem); phaseResult = r.phaseResult; gate = r.gate
    } else if (phase === 'workhorse') {
      phaseResult = await (deps.build || buildPhase)(workItem, deps.generation); gate = null
    } else if (phase === 'draft-PR') {
      const r = await (deps.draftPR || draftPRPhase)(workItem); phaseResult = r.phaseResult; gate = null; sideEffect = r.sideEffect
    } else if (phase === 'test-pilot') {
      phaseResult = await (deps.testPilot || defaultTestPilotPhase)(workItem, deps.generation); gate = null
    } else if (phase === 'mark-ready') {
      const r = await (deps.markReady || markReadyPhase)(workItem, deps.generation); phaseResult = r.phaseResult; gate = null; sideEffect = r.sideEffect
    } else if ((phase === 'review-plan' || phase === 'review-tasks') && deps.reviewDoc) {
      const doc = phase === 'review-plan' ? 'plan' : 'tasks'
      const r = await deps.reviewDoc(doc, workItem); phaseResult = r.phaseResult; gate = r.gate; persist = r.persist || null
    } else if ((phase === 'plan' || phase === 'tasks') && deps.produce) {
      phaseResult = await deps.produce(phase, workItem); gate = null
    } else {
      phaseResult = await (deps.phaseLeaf || defaultPhaseLeaf)(phase, workItem)
      gate = await (deps.gateRead || (async () => null))(phase, workItem)
    }
    // #118 "Every phase" tail: journal + cursor (+ set-gate at review phases, chained first — FR-4
    // persist order) land in ONE read-back-confirmed 'save phase progress' leaf. The advance/park
    // decision is the in-process twin, derived BEFORE the persist; a park still records the journal
    // entry (and any set-gate side effect) durably but leaves the cursor untouched (journalOnly),
    // so a resume re-enters the parked phase instead of skipping it.
    const decision = await phaseStep(phaseResult, gate)
    const proceed = decision.action === 'proceed'
    const saved = await persistPhase(workItem, {
      sideEffectCmd: (persist && persist.sideEffectCmd) || null,
      journalPayload: (persist && persist.journalPayload) ||
        { phase, gate, confidence: phaseResult.confidence, assumptions: phaseResult.assumptions || [] },
      step: i, phase, sideEffect,
      journalOnly: !proceed,
      recordCost: true,     // #130: fold this phase's cost telemetry into the save leaf
      // #130: on a park, fold a `parked` terminal marker into the same save so token_trend/run_watch
      // can classify the run (parkFromPhases journals nothing of its own).
      parkReason: !proceed ? (phaseResult.parkReason || decision.reason) : null,
    })
    // FR-4/UFR-2: a failed durable phase-progress write must never advance (and never park silently
    // on unrecorded state) — park naming the durable-write failure.
    if (!saved.ok) {
      return parkFromPhases(workItem, deps.generation, deps.root, phase,
        `phase progress not recorded (${saved.error || 'durable write failed'}) — UFR-2/FR-4`)
    }
    if (!proceed) {
      return parkFromPhases(workItem, deps.generation, deps.root, phase,
        phaseResult.parkReason || decision.reason)
    }
  }
  // Unreachable in normal operation — the 'ship' phase always returns first. Reaching here means
  // PHASES lacks 'ship' (an invariant violation), so park defensively rather than claim ready.
  return { outcome: 'parked', phase: 'ship', reason: 'phase loop ended without reaching ship (no ship phase?)' }
}

// #86 verdict -> the gate phase_step.decide consumes.
function verdictToGate(verdict) {
  return verdict && verdict.gate === 'clean' ? 'passed' : 'changes-requested'
}

// Render the loop's uniform readout (from its own verdict record, which carries parentOrigin via the
// extras channel) and post it at the park (no PR yet -> readout_post records to the store). FR-6/UFR-1.
async function renderAndPostReadout(workItem, runDir, verdict, opts) {
  opts = opts || {}
  const recPath = `${runDir}/terminal-record.json`
  const runId = opts.runId || `review-code-${workItem}`
  const lease = opts.lease || undefined
  // Composed Python-side from the run's on-disk state (round-records.json + review-telemetry.json)
  // so the evidence-bodied verdict never crosses a courier writeFile (payload-stage-failed class).
  const recWrite = await writeTerminalRecord(recPath, verdict || {}, { runId, lease, runDir })
  if (!recWrite.ok) return { ok: false, reason: recWrite.reason || 'terminal-record-write-failed' }
  // FR-5 (cwd-rooting): courier_exec's rootedCommand pins the loop_readout.py call to the repo
  // root when __SR_ROOT is set — same as renderReadout in frontHalfBoundary. The render is a dumb
  // pipe (run a command, echo stdout), so it rides the courier: pinned cheapest + one-shot retry.
  let text = ''
  try {
    text = await courier.runCourierText(
      'readout',
      `python3 ${libPath('loop_readout.py')} --record ${shq(recPath)}`)
  } catch (_e) {
    text = ''   // transport drop: post the bare park reason path below (best-effort render)
  }
  try {
    await courier.runCourierJson(
      'post readout',
      `python3 ${libPath('readout_post.py')} --work-item ${shq(workItem)} --reason ${shq(String(text))}`,
      { require: ['posted'], retryRealFailure: false },
    )
  } catch (_e) {
    // best-effort: a courier transport failure must not abort review-code parking
  }
  return { ok: true }
}
module.exports.renderAndPostReadout = renderAndPostReadout

// the review-code phase: drive the shared loop, map its terminal to advance/park, stamp covers on a
// pure `clean` (X'), and surface the readout at a park. Returns { phaseResult, gate } for runPhases.
async function reviewCodePhase(workItem, opts) {
  opts = opts || {}
  const runDir = opts.runDir || (opts.runDirSuffix
    ? `/tmp/showrunner-${workItem}-review-code-${safeRunKey(opts.runDirSuffix)}`
  : `/tmp/showrunner-${workItem}-review-code`)
  // fold 2 (#141; #211 decision shape): ONE gather leaf does the run-dir mkdir + resume DECISION +
  // round-1 plan + entry coverage read (no records ride up; the code leg has no deferred-set seed —
  // doc-only — but the round-1 tally still folds via the gathered deferredSet). Gather failure ->
  // null: fall back to a plain mkdir + the panel's own reads.
  const coverageDecisionPath = joinPath(runDir, 'review-coverage-decisions.json')
  const setup = await gatherReviewSetup({
    runDir, reviewerSet: REVIEW_CODE_REVIEWERS, context: { workItem, coverageDecisionPath },
    legKind: { panel: true, code: true }, ioApi: io(),
  })
  if (!setup) await io().mkdirp(runDir)
  // FIX A: when opts.worktree is absent, resolve the build worktree via resolveBuildTarget (the
  // stubbable seam). Explicit opts.worktree always wins (loop-smoke + targeted-smoke pass it). On
  // a production call (runPhases -> reviewCodePhase(workItem) with no opts), resolution runs and
  // fails CLOSED on error — never fall back to reviewing root (that IS the original bug).
  let resolvedWorktree = opts.worktree || null
  let resolvedHead = opts.expectedHead || null
  let resolvedConfig = null
  let cwdHeadBefore = null
  let resolvedViaGather = false
  if (!opts.worktree) {
    const resolver = opts.resolveTarget || resolveBuildTarget
    const resolved = await resolver(workItem)
    if (!resolved) {
      return {
        phaseResult: { confidence: 'low', assumptions: ['review-code: could not resolve the build worktree — refusing to review the showrunner tree'] },
        gate: 'changes-requested',
      }
    }
    resolvedWorktree = resolved.worktree
    resolvedHead = resolved.expectedHead
    // #118 review-code entry fold: 'resolve review target' is the stretch's ONE gather — it also
    // carries the review config and the CWD head, so no separate config / rev-parse leaves fire on
    // the production path. A resolver stub that omits them (older seam) falls back below.
    resolvedConfig = _coerceObj(resolved.config)
    cwdHeadBefore = resolved.cwdHead || null
    resolvedViaGather = true
  }
  const initialHead = resolvedHead || null
  // The head re-check only fires when the head was supplied EXTERNALLY (opts.expectedHead —
  // test-pilot stabilization / smokes): it verifies the tree is where the caller believes. When the
  // gather just read the head itself, re-reading the same value is a redundant leaf (matrix fold).
  if (resolvedHead && !resolvedViaGather) {
    const actual = await resolveHead(resolvedWorktree || null, opts.ref || 'HEAD')
    if (!actual || actual !== resolvedHead) {
      return { phaseResult: { confidence: 'low', assumptions: [`review-code target head mismatch: expected ${resolvedHead}, got ${actual || 'unknown'}`] }, gate: 'changes-requested' }
    }
  }
  const targetWorktree = resolvedWorktree || null
  // premortem-002: the fixer is a freeform subagent that receives the target worktree only as a TEXT
  // hint (withTargetCommandPrompts retargets just the "Run exactly this" courier prompts). If it
  // commits to the showrunner CWD instead of the target tree, the target HEAD never advances, the
  // expectedHead checks still pass (both = pre-fix HEAD), and a stale `clean` covers-stamp would
  // publish unmodified code. Snapshot CWD HEAD so we can detect that divergence after the loop
  // (carried by the gather on the production path; read here for the explicit-worktree branch).
  if (cwdHeadBefore == null && targetWorktree && resolvedHead) {
    cwdHeadBefore = await resolveHead(null, opts.ref || 'HEAD')
  }
  const cfg = (resolvedConfig && typeof resolvedConfig === 'object') ? resolvedConfig
    : await execJson(
        inWorktree(`python3 ${libPath('review_code_config.py')} --root "$(git rev-parse --show-toplevel)"`, targetWorktree), 'read review config')
  const leaves = reviewCodeLeaves((cfg && cfg.tiers) || {}, {
    target: { worktree: resolvedWorktree, head: resolvedHead },
  })
  const verdict = await runReviewCodePanel({
    runDir,
    context: { workItem, target: { worktree: resolvedWorktree, head: resolvedHead }, coverageDecisionPath, synthesisVerificationRoot: targetWorktree },
    rubric: 'review-base',
    verifyCommand: (cfg && cfg.verifyCommand) || 'none', leaves, worktree: targetWorktree,
    preloaded: setup || undefined,
  })
  const terminal = (verdict && verdict.terminal) || 'halted'
  const finalHead = resolvedHead
    ? await resolveHead(resolvedWorktree || null, opts.ref || 'HEAD')
    : null
  if (resolvedHead && !finalHead) {
    return { phaseResult: { confidence: 'low', assumptions: ['review-code final target head could not be resolved'] }, gate: 'changes-requested', terminal, head: null, changed: false }
  }
  // #104's advance/park mapping, read off the terminal (plan Key decision 2).
  if (!ADVANCE_TERMINALS.has(terminal)) {
    const readout = await renderAndPostReadout(workItem, runDir, verdict)
    if (!readout || !readout.ok) {
      return {
        phaseResult: { confidence: 'low', assumptions: [`review-code readout failed: ${(readout && readout.reason) || 'unknown'}`] },
        gate: 'changes-requested', terminal, head: finalHead,
        changed: !!(initialHead && finalHead && initialHead !== finalHead),
      }
    }
    // #212: name the terminal + the panel's honest reason on parkDetail so the workflow park reads
    // e.g. "review requested changes — cannot-certify: premortem-reviewer returned no verification
    // receipt after retry (receipt-missing — uncertifiable)" instead of the bare flatten. Empty
    // assumptions → phase_step routes this to park_changes_requested (not park_assumption).
    const parkDetail = `${terminal}: ${(verdict && verdict.reason) || 'review not certified'}`
    return { phaseResult: { confidence: 'high', assumptions: [], parkDetail }, gate: 'changes-requested', terminal, head: finalHead, changed: !!(initialHead && finalHead && initialHead !== finalHead) }
  }
  // premortem-002 fail-closed: an advancing terminal means we're about to certify the target HEAD. If
  // the CWD advanced while the target HEAD did not, the fixer's commits landed outside the shipped tree
  // — refuse to advance/stamp rather than certify (and ship) code the fixes never touched.
  if (targetWorktree && resolvedHead) {
    const cwdHeadAfter = await resolveHead(null, opts.ref || 'HEAD')
    const cwdMoved = cwdHeadBefore && cwdHeadAfter && cwdHeadBefore !== cwdHeadAfter
    const targetMoved = initialHead && finalHead && initialHead !== finalHead
    if (cwdMoved && !targetMoved) {
      return { phaseResult: { confidence: 'low', assumptions: ['review-code fixes landed outside the target worktree (cwd HEAD advanced, target HEAD did not) — refusing to stamp coverage'] }, gate: 'changes-requested', terminal, head: finalHead, changed: false }
    }
  }
  // FR-9: stamp covers = X' ONLY on a pure `clean`; every other terminal already parked above.
  // prov_entry resolves the build-branch tip (= X' after the fixer's commits).
  if (terminal === 'clean') {
    const targetArgs = resolvedWorktree || resolvedHead
      ? ` --worktree ${shq(resolvedWorktree || procCwd())}${finalHead ? ` --head ${shq(finalHead)}` : ''}`
      : ''
    let prov = null
    try {
      prov = await courier.runCourierJson(
        'stamp review coverage',
        `python3 ${libPath('prov_entry.py')} --step review --work-item ${shq(workItem)}${targetArgs}`,
        { require: ['ok'], retryRealFailure: false },
      )
    } catch (_) {
      prov = { ok: false, error: 'unreadable' }
    }
    if (!prov.ok) {
      // UFR-2: the covers-stamp write failed -> park (low confidence), do NOT assert ship-ready.
      return { phaseResult: { confidence: 'low', assumptions: ['review covers stamp not recorded: ' + (prov.error || 'unknown')] }, gate: 'changes-requested' }
    }
  }
  return {
    phaseResult: { confidence: 'high', assumptions: [] },
    gate: 'passed',
    terminal,
    head: finalHead,
    changed: !!(initialHead && finalHead && initialHead !== finalHead),
    reviewCoverageHead: terminal === 'clean' ? (finalHead || undefined) : undefined,
    verifyPassedHead: finalHead || undefined,
  }
}

// resolveHead: dumb-pipe git rev-parse via the exec courier (pinned cheapest, one-shot retry).
// Production review-code resolves heads inside the folded 'resolve review target' gather; this
// remains for the explicit-worktree branch (test-pilot stabilization) and post-loop head checks.
async function resolveHead(worktree, ref) {
  const cmd = worktree
    ? `git -C ${shq(worktree)} rev-parse ${shq(ref || 'HEAD')}`
    : `git rev-parse ${shq(ref || 'HEAD')}`
  try {
    const out = await execText(cmd, 'resolve head')
    return out || null
  } catch (_) {
    return null
  }
}

// the native "workhorse" build phase (#87) — implement the approved tasks doc task-by-task with a
// per-task review + bounded fix loop, one whole-branch final review, and provenance written once.
// All of that orchestration lives in build_phase.js; the spine just delegates, threading the lease
// generation reconcile() acquired so the build can fence every branch-mutating boundary (UFR-10).
const buildPhase = (workItem, generation) => require('./build_phase.js').buildPhase(workItem, generation)

// Resolve the build worktree + expected head for review-code. Mirrors build_phase.js's execJson
// pattern (cheap exec dumb-pipe, NOT a genuine agent) so the call is deterministic + stubbable.
// Runs build_entry.py WITHOUT --generation (idempotent: reclaim_or_create returns REUSED for an
// existing clean worktree; lockGeneration is only set when --generation is passed).
// #118 review-code entry fold: the same gather also reads the review config (review_code_config.py
// in the target worktree) and the CWD head — the whole entry stretch is this ONE leaf. Both extras
// are best-effort (null on failure): config falls back to {verifyCommand:'none'} downstream, and a
// missing cwdHead only re-adds the explicit-branch rev-parse leaf.
// Returns {worktree, expectedHead, config, cwdHead} or null on any failure (caller parks on null).
async function resolveBuildTarget(workItem) {
  const script = [
    'import json, subprocess, sys',
    'wi = sys.argv[1]',
    'setup = None',
    'for _ in range(2):',
    '    try:',
    `        r = subprocess.run(["python3", ${pyLibScript('build_entry.py')}, "--work-item", wi], capture_output=True, text=True, timeout=120)`,
    '    except subprocess.TimeoutExpired:',
    '        continue',
    '    if r.returncode != 0: continue',
    '    try: setup = json.loads((r.stdout or "").strip() or "{}"); break',
    '    except Exception: continue',
    'if not setup or setup.get("error") or not setup.get("path"):',
    '    print(json.dumps({"ok": False, "error": "missing build worktree"})); raise SystemExit(0)',
    'if str(setup.get("outcome", "")).lower() == "created":',
    '    print(json.dumps({"ok": False, "error": "fresh worktree created"})); raise SystemExit(0)',
    'wt = setup["path"]',
    'head = None',
    'for _ in range(2):',
    '    try:',
    '        r = subprocess.run(["git", "-C", wt, "rev-parse", "HEAD"], capture_output=True, text=True, timeout=30)',
    '    except subprocess.TimeoutExpired:',
    '        continue',
    '    if r.returncode == 0 and (r.stdout or "").strip():',
    '        head = r.stdout.strip(); break',
    'if not head:',
    '    print(json.dumps({"ok": False, "error": "missing target head"})); raise SystemExit(0)',
    'cfg = None',
    'try:',
    `    r = subprocess.run(["python3", ${pyLibScript('review_code_config.py')}, "--root", wt], capture_output=True, text=True, timeout=60, cwd=wt)`,
    '    if r.returncode == 0:',
    '        cfg = json.loads((r.stdout or "").strip() or "null")',
    'except Exception:',
    '    cfg = None',
    'cwd_head = None',
    'try:',
    '    r = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=30)',
    '    if r.returncode == 0 and (r.stdout or "").strip():',
    '        cwd_head = r.stdout.strip()',
    'except Exception:',
    '    cwd_head = None',
    'print(json.dumps({"ok": True, "worktree": wt, "expectedHead": head, "config": cfg, "cwdHead": cwd_head}))',
  ].join('\n')
  let setup = null
  try {
    setup = await courier.runCourierJson(
      'resolve review target',
      `python3 -c ${shq(script)} ${shq(workItem)}`,
      { require: ['ok'] },
    )
  } catch (_) {
    setup = null
  }
  if (!setup || setup.error || !setup.worktree) return null   // fail-closed: no usable worktree
  return {
    worktree: setup.worktree,
    expectedHead: setup.expectedHead,
    config: setup.config != null ? setup.config : null,
    cwdHead: setup.cwdHead || null,
  }
}

module.exports.verdictToGate = verdictToGate
module.exports.reviewCodePhase = reviewCodePhase
module.exports.resolveBuildTarget = resolveBuildTarget
module.exports.runReviewCodePanel = runReviewCodePanel
module.exports.buildPhase = buildPhase

// loadPr: read the checkpointed PR before the ship phase — a dumb-pipe read via the exec courier
// (pinned cheapest + one-shot retry, #118). The cursor itself is written by the per-phase
// persistPhase tail; there is no separate checkpoint_entry write leaf anymore.
async function loadPr(workItem) {
  const out = await execJson(
    `python3 ${libPath('checkpoint_entry.py')} --work-item ${shq(workItem)} --read-pr`, 'read pr')
  return (out && out.pr !== undefined) ? out.pr : null
}

// draft-PR: one folded courier leaf returning {ok, pr, read_back, reason?}.
async function draftPRPhase(workItem) {
  const _srBaseForPR = (typeof globalThis !== 'undefined' && globalThis.__SR_BASE) ? String(globalThis.__SR_BASE) : null
  const _prBaseArg = _srBaseForPR ? ` --base ${shq(_srBaseForPR)}` : ''
  let out = null
  try {
    out = await courier.runCourierJson(
      'open draft PR',
      `python3 ${libPath('pr_entry.py')} --step draft --work-item ${shq(workItem)}${_prBaseArg}`,
      { require: ['ok', 'read_back'], retryRealFailure: false },
    )
  } catch (_e) {
    // courier transport failure (dropped/garbled stdout twice) — park, never crash the run; a PR the
    // first attempt may have created is re-adopted idempotently by pr_entry on the next run.
    out = null
  }
  if (!out || !out.ok || !out.pr || !out.read_back) {
    return {
      phaseResult: { confidence: 'low', assumptions: [(out && out.reason) || 'draft-PR gated'] },
      sideEffect: null,
    }
  }
  return { phaseResult: { confidence: 'high', assumptions: [] }, sideEffect: { pr: out.pr } }
}

// fill-dod: the "build/ship legs fill it" leg from issue #228's own design — the draft-PR
// step seeds the disposition table skeleton; a MODEL leaf PROPOSES dispositions from the
// run's real evidence, and the deterministic splice CLI (dod_fill_cli.py) holds the pen
// (PR #251 review: a model rewriting the full body at a certification boundary risked
// truncating the stubbed-seams disclosure, clobbering concurrent edits, and fabricating
// evidence — the CLI touches only matching table cells, mechanically verifies deferred
// issues resolve and path-shaped evidence exists, and read-back-confirms the write).
// Honesty contract unchanged: a row the model cannot evidence is omitted, stays blank,
// and the (unchanged, fail-closed) gate parks with the same honest reason.
async function proposeDodDispositions(workItem, prNumber) {
  const absRoot = checkoutRoot()
  try {
    const raw = await agent(
      `You are the DoD disposition-proposal leg for work-item ${workItem} (issue #228). ` +
      `Draft PR #${prNumber} carries a "DoD dispositions" table seeded from the spec's ` +
      `Definition-of-done section. Propose dispositions from REAL run evidence and return ` +
      `them as JSON — you do NOT edit the PR yourself; a deterministic splice tool applies ` +
      `your rows and mechanically verifies them.\n` +
      `Work from the repo root at ${absRoot} (run every command from there).\n` +
      `Steps:\n` +
      `1. Spec: run python3 ${libPath('definition_doc.py')} path --work-item ${shq(workItem)} ` +
      `--doc spec --root ${shq(absRoot)} and read the Definition-of-done bullets from that file.\n` +
      `2. Current table: gh pr view ${shq(String(prNumber))} --json body.\n` +
      `3. Evidence, per bullet — use only what actually exists: the PR diff ` +
      `(gh pr diff ${shq(String(prNumber))}), the head branch (gh pr view ${shq(String(prNumber))} --json headRefName), ` +
      `the build/final-review records (python3 ${libPath('build_state_cli.py')} gather ` +
      `--work-item ${shq(workItem)} --branch <that headRefName>), the test-pilot status record ` +
      `(test-pilot-status.json under the control-plane store for this work-item), and CI check state.\n` +
      `4. For each bullet you can HONESTLY disposition: "done" needs a concrete evidence ` +
      `pointer (command output, record path, diff line); "deferred" needs an ALREADY-FILED ` +
      `issue number (#NNN) plus a one-line reason. NEVER invent evidence or issue numbers — ` +
      `deferred issues are mechanically resolved against GitHub and path-shaped evidence is ` +
      `existence-checked, so a fabricated row is rejected and the gate parks. If a bullet has ` +
      `no real evidence, OMIT it (the row stays blank and the gate parks honestly).\n` +
      `Return ONLY JSON {"ok": true, "rows": [{"bullet": "<bullet text exactly as it appears ` +
      `in the spec/table>", "disposition": "done"|"deferred", "detail": "<evidence pointer or ` +
      `#NNN + reason>"}]} (ok=false with "reason" if you could not read the spec or PR).`,
      { label: 'fill-dod', schema: { type: 'object', required: ['ok'] } })
    // Boundary coercion (#115 class, observed live in run wf_a9654118: the leaf returned
    // ok:'true' and rows as a JSON STRING). ok must compare against the string form too —
    // 'false' is truthy, so a plain truthiness check would read a refusal as consent.
    const obj = _coerceObj(raw)
    if (!obj || typeof obj !== 'object' || Array.isArray(obj)) return null
    const rows = _coerceObj(obj.rows)
    return {
      ok: obj.ok === true || obj.ok === 'true',
      rows: Array.isArray(rows) ? rows : [],
    }
  } catch (_e) {
    return null   // proposal failure -> the gate re-run below is skipped; the original park stands
  }
}

// mark-ready: gate courier leaf; on a DoD-table park (gate === 'dod', pr_entry's machine
// field — never the reason string, CONVENTIONS §11): fence the lease (UFR-4 — the splice
// is a PR-mutating boundary), ONE proposal leaf, ONE deterministic splice, ONE gate
// re-decide. DoD-less runs (quick route, dispositions already filled) pay no extra leaf.
async function markReadyPhase(workItem, generation) {
  const gate = async () => {
    try {
      return await courier.runCourierJson(
        'mark PR ready',
        `python3 ${libPath('pr_entry.py')} --step mark-ready --work-item ${shq(workItem)}`,
        { require: ['ok', 'read_back'], retryRealFailure: false },
      )
    } catch (_e) {
      return null   // courier transport failure — park, never crash the run
    }
  }
  let out = await gate()
  if (out && !out.ok && out.gate === 'dod' && out.pr != null) {
    // Settle CI BEFORE the proposal leaf (finding #12, run fdfad511: the fixture's
    // "green CI" DoD bullet is undissposable while the draft PR's checks are still
    // running — a fast spine reaches this gate ~2 min after opening the PR, the leaf
    // honestly omits the bullet, and the run parks on a race, not a defect). Pending
    // is WAIT, not FIX (#11); the settle CLI returns immediately when nothing is
    // pending, so the common case costs one instant leaf. Best-effort: a settle
    // transport failure or exhausted budget falls through to the proposal — the leaf
    // then evidences what it can and the gate stays honest.
    // The settle CLI reads the PR head's checks via ship_phase --emit-checks, whose
    // stale guard compares the local head at cwd to the remote PR head — from the
    // checkout root (base branch) that ALWAYS reads stale and short-circuits without
    // waiting (PR #261 review finding). Resolve the build worktree first, exactly
    // like the ship loop; if it cannot be resolved, skip the wait (best-effort).
    try {
      const target = await resolveBuildTarget(workItem).catch(() => null)
      const wt = target && target.worktree
      if (wt) {
        await courier.runCourierJson(
          'wait for CI to settle',
          `python3 ${libPath('ci_settle_cli.py')} --work-item ${shq(workItem)} --worktree ${shq(wt)} --timeout-sec 540`,
          { require: ['settled'], retryRealFailure: false },
        )
      }
    } catch (_e) { /* best-effort wait — the propose leaf re-reads check state itself */ }
    const proposed = await proposeDodDispositions(workItem, out.pr)
    if (proposed && proposed.ok && Array.isArray(proposed.rows) && proposed.rows.length) {
      // UFR-4: the splice mutates the PR — fence the lease generation first, park on loss.
      const fenced = generation == null ? true : await shipFenceOrPark(workItem, generation, checkoutRoot())
      if (!fenced) {
        return { phaseResult: { confidence: 'low', assumptions: ['lease lost before the DoD disposition splice — park (UFR-4)'] }, sideEffect: null }
      }
      let spliced = null
      try {
        const rowsPath = joinPath(io().tmpdir(), `showrunner-${workItem}-dod-rows.json`)
        await io().writeFile(rowsPath, JSON.stringify(proposed.rows))
        spliced = await courier.runCourierJson(
          'splice DoD dispositions',
          `python3 ${libPath('dod_fill_cli.py')} --pr ${shq(String(out.pr))} --rows ${shq(rowsPath)} --root .`,
          { require: ['ok'], retryRealFailure: false },
        )
      } catch (_e) {
        spliced = null   // splice transport failure -> original honest park stands
      }
      if (spliced && spliced.ok) {
        const retry = await gate()
        out = retry || out   // a transport failure on the re-decide keeps the specific DoD park reason
      }
    }
  }
  if (!out || !out.ok || !out.read_back) {
    return { phaseResult: { confidence: 'low', assumptions: [(out && out.reason) || 'mark-ready gated'] }, sideEffect: null }
  }
  return { phaseResult: { confidence: 'high', assumptions: [] }, sideEffect: { ready: true } }
}

module.exports.draftPRPhase = draftPRPhase
module.exports.markReadyPhase = markReadyPhase
module.exports.testPilotPhase = testPilotPhase
module.exports.defaultTestPilotPhase = defaultTestPilotPhase
module.exports.testPilotDeps = testPilotDeps

// renew-then-fence the lease generation immediately before a branch-/PR-mutating boundary (UFR-4).
// Fail-closed: a null generation or a lost/unreadable lease returns false -> the caller parks BEFORE
// any mutation. Mirrors build_phase.js's fenceOrPark; #118 folds this seam spine-wide.
async function shipFenceOrPark(workItem, generation, root) {
  if (generation == null) return false
  const cmd = fenceCliCmd(workItem, generation, root)
  if (!cmd) return false
  const out = await execJson(cmd, 'fence lease')
  return !!(out && out.ok)
}
module.exports.shipFenceOrPark = shipFenceOrPark

function parseCiChecks(checks) {
  if (checks == null) return { error: 'CI status could not be read' }
  if (!Array.isArray(checks) && checks.stale) return { stale: true }
  if (!Array.isArray(checks) && checks.error) return { error: checks.error || 'CI status could not be read' }
  return { checks: Array.isArray(checks) ? checks : [] }
}

async function checkShipReadiness(workItem, worktree, baseName, generation, checksOnly, root) {
  const baseArg = baseName ? ` --base ${shq(baseName)}` : ''
  const wtArg = worktree ? ` --worktree ${shq(worktree)}` : ''
  const genArg = generation != null ? ` --generation ${shq(String(generation))}` : ''
  const checksArg = checksOnly ? ' --checks-only' : ''
  const r = checkoutRoot(root)
  const rootArg = r ? ` --root ${shq(r)}` : ''
  return courier.runCourierJson(
    'check ship-readiness',
    `python3 ${libPath('ship_phase.py')} --step ship-readiness --work-item ${shq(workItem)}` +
    `${baseArg}${wtArg}${genArg}${checksArg}${rootArg}`,
    { require: checksOnly ? ['checks'] : ['ok', 'reconcile', 'freshness', 'checks'] },
  )
}

async function prepareCiFix(workItem, failing) {
  return courier.runCourierJson(
    'prepare CI fix',
    `python3 ${libPath('ship_phase.py')} --step prepare-ci-fix --work-item ${shq(workItem)} --failing ${shq(JSON.stringify(failing || []))}`,
    { require: ['action', 'read_back'], retryRealFailure: false },
  )
}

async function pushCiFixRecheck(workItem, worktree) {
  const wtArg = worktree ? ` --worktree ${shq(worktree)}` : ''
  return courier.runCourierJson(
    'push CI fix + recheck',
    `python3 ${libPath('ship_phase.py')} --step push-ci-fix-recheck --work-item ${shq(workItem)}${wtArg}`,
    { require: ['read_back', 'checks'], retryRealFailure: false },
  )
}

async function postReadout(workItem, pr, args) {
  const prNum = pr && pr.number ? ` --pr ${shq(String(pr.number))}` : ''
  // #130: the ship hand-back is the run's terminal leaf. Fold the terminal marker (completed vs
  // parked — the durable signal token_trend.py buckets on) and ship's cost telemetry into it, so
  // ship rides no new courier leaf (#118). Both are best-effort inside readout_post.py.
  const termArg = args.terminal ? ` --terminal ${shq(args.terminal)}` : ''
  const costArg = args.costBody ? ` --cost-payload ${shq(JSON.stringify(args.costBody))}` : ''
  const cmd = args.ctx
    ? `python3 ${libPath('readout_post.py')} --work-item ${shq(workItem)}${prNum}${termArg}${costArg} --ctx ${shq(JSON.stringify(args.ctx))}`
    : `python3 ${libPath('readout_post.py')} --work-item ${shq(workItem)} --reason ${shq(args.reason || '')}${prNum}${termArg}${costArg}`
  try {
    return await courier.runCourierJson('post readout', cmd, { require: ['posted'], retryRealFailure: false })
  } catch (_e) {
    return { posted: false, recorded: false, error: 'courier transport failed' }
  }
}

// ── Native back-half seam map (for #118 courier-surface collapse, which sequences AFTER #120) ──
// shipPhase orchestrates four SEPARABLE per-stretch seams, each with the same shape:
//   world-read → renew-then-fence(generation) → mutate (git/gh leaf) → read-back-confirm.
//   1. entry reconcile  — ship_phase.py --step reconcile-head  (idempotent push-reconcile)
//   2. catch-up stretch — ship_phase.py --step freshen          (merge base / conflict-abort / push)
//   3. ci-fix stretch   — ship_phase.py --step {ci,ci-decide,ci-record,fix-push,revert-draft}
//   4. hand-back        — readout_post.py --ctx                 (best-effort; never ship-gated)
// FENCE/LEASE SEAM: the lease generation is threaded from reconcile() → runPhases(deps.generation)
//   → shipPhase(_, _, generation); every mutating boundary calls shipFenceOrPark(workItem, generation)
//   (renew-then-fence, fail-closed) BEFORE the mutation — the same generation build_phase.js fences on.
// IDEMPOTENCY SEAM: create / ready-flip / draft-flip / push-reconcile route through idempotent_write.py
//   (read-reality, apply-once). #118 generalizes that primitive to EVERY durable write (its FR-4).
// #118 may fold/relabel these leaves; #120 deliberately leaves them as clean, un-folded seams.
async function shipPhase(workItem, pr, generation) {
  const storeRoot = checkoutRoot()
  const target = await resolveBuildTarget(workItem)
  const worktree = target && target.worktree ? target.worktree : null
  if (!worktree) {
    return park(workItem, pr, 'could not resolve the build worktree for the back-half — park (no mutation against the repo root)')
  }
  const _srBase = (typeof globalThis !== 'undefined' && globalThis.__SR_BASE) ? String(globalThis.__SR_BASE) : null
  const baseName = _srBase || ''
  if (!(await shipFenceOrPark(workItem, generation, storeRoot))) {
    return park(workItem, pr, 'lease lost before reconciling the PR head — park (UFR-4)')
  }
  let ready
  try {
    ready = await checkShipReadiness(workItem, worktree, baseName, generation, false, storeRoot)
  } catch (_e) {
    return park(workItem, pr, 'branch readiness could not be confirmed (unreadable) — park (UFR-2)')
  }
  if (!ready || !ready.ok) {
    const fresh = ready && ready.freshness
    if (fresh && fresh.decision === 'give_up_notify') {
      return park(workItem, pr, 'branch is behind its base after the catch-up limit — update it before merge')
    }
    if (fresh && fresh.decision === 'conflict') {
      return park(workItem, pr, 'bringing in the base conflicts — undone (branch unchanged); please resolve and re-run')
    }
    // fence first: on a lost lease ship_phase.py emits reconcile:{ok:false,reason:'unread'} TOO, so
    // checking reconcile first would mask the lease-loss diagnostic behind a generic reconcile park.
    if (ready && ready.fence && !ready.fence.ok) {
      return park(workItem, pr, 'lease lost before base catch-up — park (UFR-4)')
    }
    const reconcile = ready && ready.reconcile
    if (reconcile && !reconcile.ok) {
      return park(workItem, pr, `could not reconcile the PR head before judging readiness (${reconcile.reason || 'unreadable'})`)
    }
    return park(workItem, pr, `branch freshness could not be confirmed (${(fresh && fresh.decision) || 'unreadable'}) — park (UFR-2)`)
  }
  const integrated = !!ready.integrated
  let ciChecks = ready.checks
  const MAX_CI_PASSES = 6
  // Consecutive settle-leaf budget: each leaf waits ≤540s (the bash_timeout hook floors the
  // Bash tool at 600000ms, so ONE leaf can never outwait a long CI run), and real target
  // projects (weekly-eats, loupe) have CI well past 10 minutes. 4 rounds ≈ 36 min of total
  // patience (≥2x a 15-min run) — per consecutive streak, and only fully grantable while
  // MAX_CI_PASSES budget remains (fix rounds spend from the same pass budget). The counter
  // resets whenever checks actually settle or a fix is pushed (a new CI run deserves fresh
  // patience); MAX_CI_PASSES still bounds the loop.
  const MAX_SETTLE_ROUNDS = 4
  let settleRounds = 0
  for (let pass = 0; pass < MAX_CI_PASSES; pass += 1) {
    const parsed = parseCiChecks(ciChecks)
    if (parsed.error) {
      return park(workItem, pr, typeof parsed.error === 'string' ? parsed.error : 'CI status could not be read')
    }
    if (parsed.stale) {
      try {
        const recheck = await checkShipReadiness(workItem, worktree, baseName, generation, true, storeRoot)
        ciChecks = recheck && recheck.checks
      } catch (_e) {
        return park(workItem, pr, 'CI status could not be read')
      }
      continue
    }
    const ciRes = ciStatusTwin.classify(parsed.checks)
    if (ciRes.status === 'green') {
      return shipHandback(workItem, pr, { ready: true, ci: 'green', integrated, reason: 'merge-ready: CI green and branch up to date — awaiting owner merge' })
    }
    if (ciRes.status === 'none') {
      return shipHandback(workItem, pr, { ready: true, ci: 'none', integrated, reason: 'merge-ready: no required checks ran on the ready PR — confirm checks before merging' })
    }
    if (ciRes.status === 'pending') {
      // The live-run settle-poll deferred from #120 (0.10.0 qualification finding: pending
      // classified as red dispatched a CI fixer at checks that were merely running). CI
      // re-runs are near-deterministic on spec-driven runs because the DoD fill leg edits
      // the PR body and ci.yml's pull_request types include `edited` — pending is WAIT,
      // not FIX. One bounded courier leaf does the whole wait (deterministic, journaled);
      // its budget (540s) sits under the Bash tool ceiling the bash_timeout hook floors
      // to 600000ms, so the CLI's own honest budget-exhausted return is always reachable.
      settleRounds += 1
      let settled = null
      try {
        settled = await courier.runCourierJson(
          'wait for CI to settle',
          `python3 ${libPath('ci_settle_cli.py')} --work-item ${shq(workItem)}${worktree ? ` --worktree ${shq(worktree)}` : ''} --timeout-sec 540`,
          { require: ['settled'], retryRealFailure: false },
        )
      } catch (_e) {
        return park(workItem, pr, 'CI status could not be read while waiting for checks to settle')
      }
      if (!settled || settled.settled !== true) {
        if (settled && settled.checks && !Array.isArray(settled.checks) && settled.checks !== null) { ciChecks = settled.checks; continue }
        if (settleRounds < MAX_SETTLE_ROUNDS && settled && Array.isArray(settled.checks)) {
          ciChecks = settled.checks   // long CI run — another bounded round, budget above
          continue
        }
        const stillPending = (settled && Array.isArray(settled.checks))
          ? ciStatusTwin.classify(settled.checks).pending
          : (ciRes.pending || [])
        return park(workItem, pr, `CI checks still pending after the settle wait (${stillPending.join(', ')}) — confirm checks and re-run`)
      }
      settleRounds = 0
      ciChecks = settled.checks
      continue
    }
    let decided = null
    try {
      decided = await prepareCiFix(workItem, ciRes.failing)
    } catch (_e) {
      return park(workItem, pr, 'CI fix preparation could not be confirmed (unreadable) — park (UFR-2)')
    }
    if (!decided || decided.action === 'revert_and_gate') {
      if (!(await shipFenceOrPark(workItem, generation, storeRoot))) { return park(workItem, pr, 'lease lost before return-to-draft — park (UFR-4)') }
      const rd = await execJson(
        `python3 ${libPath('ship_phase.py')} --step revert-draft --work-item ${shq(workItem)}`, 'revert draft')
      const reverted = !!(rd && rd.ok)
      return shipHandback(workItem, pr, { ready: false, ci: 'red', integrated, reverted,
        reason: reverted
          ? 'checks could not be made to pass — returned to draft for you'
          : `checks could not be made to pass, and the PR could NOT be returned to draft (${(rd && rd.reason) || 'unknown'}) — please set it to draft before merging` })
    }
    if (decided.action === 'fix') {
      if (!decided.ok || decided.read_back === false) {
        return park(workItem, pr, 'could not record the CI-fix round (durable write failed) — park before the fix push (UFR-5)')
      }
      if (!(await shipFenceOrPark(workItem, generation, storeRoot))) { return park(workItem, pr, 'lease lost before CI fix push — park (UFR-4)') }
      await agent(
        `Fix the failing CI checks for this PR in the build worktree${worktree ? ' at ' + worktree : ''}: ${ciRes.failing.join(', ')}. ` +
        `Make ONLY the code changes needed to make the checks pass; do not write CI-log text into a commit.`,
        { label: 'fix-ci' })
      let pushed
      try {
        pushed = await pushCiFixRecheck(workItem, worktree)
      } catch (_e) {
        return park(workItem, pr, 'could not push the CI fix (transport failed) — park, no false ready')
      }
      if (!pushed || !pushed.pushed || pushed.read_back === false) {
        return park(workItem, pr, `could not push the CI fix (${(pushed && pushed.reason) || 'unknown'}) — park, no false ready`)
      }
      settleRounds = 0   // fresh CI run after the fix push — fresh settle patience
      ciChecks = pushed.checks
      continue
    }
    return park(workItem, pr, 'unexpected ci-decide action (' + (decided && decided.action) + ') — park (fail-closed)')
  }
  return park(workItem, pr, 'checks did not complete within the bound — confirm CI before merging')
}

async function park(workItem, pr, reason, mergeReady) {
  const rPost = await postReadout(workItem, pr,
    { reason, terminal: mergeReady ? 'completed' : 'parked', costBody: phaseCostPayload('ship') })
  const delivered = rPost && (rPost.posted || rPost.recorded)
  const reasonOut = delivered
    ? reason
    : `${reason} [warning: readout could not be delivered (${(rPost && rPost.error) || 'unknown'})]`
  return { outcome: mergeReady ? 'ready' : 'parked', phase: 'ship', reason: reasonOut }
}

async function shipHandback(workItem, pr, info) {
  const prUrl = pr && pr.url ? pr.url : ''
  const ctx = {
    pr_url: prUrl,
    ci_status: info.ci === 'green' ? 'green — all required checks pass'
      : info.ci === 'none' ? 'no required checks ran on the ready PR — confirm before merging'
      : 'checks could not be made to pass — returned to draft',
    built_vs_acceptance: info.reason || '',
    smoke: ['Confirm the PR branch contains its base', 'Confirm CI on the ready head', 'Review the diff before merging'],
  }
  if (info.integrated) {
    ctx.integration_note = 'the final commit carries base integration done after the code review (the merged-in base was check-vetted, not re-reviewed)'
  }
  const rPost = await postReadout(workItem, pr,
    { ctx, terminal: info.ready ? 'completed' : 'parked', costBody: phaseCostPayload('ship') })
  const delivered = rPost && (rPost.posted || rPost.recorded)
  const reasonOut = delivered ? info.reason
    : `${info.reason} [warning: hand-back could not be delivered (${(rPost && rPost.error) || 'unknown'})]`
  return { outcome: info.ready ? 'ready' : 'parked', phase: 'ship', reason: reasonOut }
}
module.exports.shipHandback = shipHandback

module.exports.shipPhase = shipPhase
module.exports.park = park

async function defaultPhaseLeaf(_phase, _workItem) {
  return { confidence: 'high', assumptions: [] }
}

module.exports.showrunner = showrunner
module.exports.resolveIntake = resolveIntake
module.exports.recordSkippedPhases = recordSkippedPhases
module.exports.cmdRunner = cmdRunner
module.exports.reconcile = reconcile
module.exports.checkoutRoot = checkoutRoot
module.exports.runPhases = runPhases
module.exports.PHASES = PHASES
module.exports.exec = exec
module.exports.persistPhase = persistPhase
module.exports.phaseCostPayload = phaseCostPayload
module.exports.readStartupState = readStartupState
module.exports.startupStateScript = startupStateScript
module.exports.readDefinitionDraft = readDefinitionDraft
module.exports.cheapestModel = cheapestModel
module.exports.selfContained = selfContained
module.exports.authorModel = authorModel

};


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
