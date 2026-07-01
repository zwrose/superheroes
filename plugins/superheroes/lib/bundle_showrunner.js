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
const MODULES = ['circuit_breaker.js', 'loop_state.js', 'loop_synthesis.js', 'panel_tally.js',
                 'review_round_policy.js',
                 'ci_status.js', 'verify_gate.js',
                 'review_memory.js',
                 'review_panel_shell.js', 'test_pilot_phase.js', 'build_progress.js',
                 'worker_recovery.js', 'task_review.js', 'build_phase.js',
                 'model_tier.js', 'phase_step.js', 'recover.js', 'front_half.js', 'showrunner.js']

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
//      (smart) leaves get __SR_LEAF_MODEL when set (throwaway/test runs) or the session default.
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
const __realAgent = agent
globalThis.agent = function (prompt, opts) {
  var o = Object.assign({}, opts || {})
  // Dumb-pipe detection: check the INCOMING label (before __leafLabel may relabel it) to identify
  // the mechanical tier. exec and io leaves are pure side-effect executors — they ALWAYS run at the
  // cheapest model unconditionally, independent of __SR_LEAF_MODEL or any session default.
  // Genuine-LLM (smart) leaves get __SR_LEAF_MODEL when set (throwaway/test run override).
  var __isDumb = (o.label === 'exec' || o.label === 'io')
  if (__isDumb) {
    o.model = __cheapest()
  } else if (globalThis.__SR_LEAF_MODEL) {
    o.model = globalThis.__SR_LEAF_MODEL
  }
  if (!o.phase && globalThis.__SR_PHASE) o.phase = globalThis.__SR_PHASE
  if (!o.label || o.label === 'lib' || o.label === 'io') o.label = __leafLabel(String(prompt), o.label)
  return __realAgent(prompt, o)
}
globalThis.parallel = parallel
globalThis.log = (typeof log === 'function') ? log : (() => {})
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
async function __sh(cmd) { return globalThis.agent('Run exactly this command and return ONLY its stdout, unchanged:\\n\\n' + __sc(cmd), { label: 'io' }) }
function __join() { return Array.prototype.slice.call(arguments).join('/').replace(/\\/+/g, '/') }
function __contentHash(text) {
  var s = String(text || '')
  var i, j, t, l = ((s.length + 8 >> 6) + 1) << 4, w = new Array(l), H = [0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19]
  var K = [0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da, 0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070, 0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2]
  s += '\x80'; while (s.length % 64 !== 56) s += '\0'
  for (i = 0; i < s.length; i += 4) w[i >> 2] = (s.charCodeAt(i) << 24) | (s.charCodeAt(i + 1) << 16) | (s.charCodeAt(i + 2) << 8) | s.charCodeAt(i + 3)
  w[l - 1] = s.length * 8
  for (i = 0; i < l;) {
    var a = H[0], b = H[1], c = H[2], d = H[3], e = H[4], f = H[5], g = H[6], h = H[7]
    for (j = 0; j < 64; j++) {
      if (j < 16) t = w[j + i]; else {
        var s0 = ((t = w[j + i - 15]) >>> 7 | t << 25) ^ (t >>> 18 | t << 14) ^ (t >>> 3)
        var s1 = ((t = w[j + i - 2]) >>> 17 | t << 15) ^ (t >>> 19 | t << 13) ^ (t >>> 10)
        t = w[j + i - 16] + s0 + w[j + i - 7] + s1
      }
      t = (h + ((e >>> 6 | e << 26) ^ (e >>> 11 | e << 21) ^ (e >>> 25 | e << 7)) + (e & f ^ ~e & g) + K[j] + t) | 0
      h = g; g = f; f = e; e = (d + t) | 0; d = c; c = b; b = a
      a = (t + (((a >>> 2 | a << 30) ^ (a >>> 13 | a << 19) ^ (a >>> 22 | a << 10)) + (a & b ^ a & c ^ b & c))) | 0
    }
    H[0] = (H[0] + a) | 0; H[1] = (H[1] + b) | 0; H[2] = (H[2] + c) | 0; H[3] = (H[3] + d) | 0
    H[4] = (H[4] + e) | 0; H[5] = (H[5] + f) | 0; H[6] = (H[6] + g) | 0; H[7] = (H[7] + h) | 0; i += 16
  }
  var out = ''
  for (i = 0; i < 8; i++) for (j = 3; j >= 0; j--) out += ('0' + ((H[i] >>> (j * 8)) & 255).toString(16)).slice(-2)
  return out
}
globalThis.io = {
  join: __join, tmpdir() { return '/tmp' },
  async mkdirp(d) { await __sh('mkdir -p ' + __q(d)) },
  async writeFile(p, s) { const b = (typeof s === 'string') ? s : JSON.stringify(s); await __sh('cat > ' + __q(p) + " <<'__SR_EOF__'\\n" + b + '\\n__SR_EOF__') },
  async readText(p) { return __sh('cat ' + __q(p) + ' 2>/dev/null || true') },
  async readJson(p, dflt) { const t = await __sh('cat ' + __q(p) + ' 2>/dev/null || true'); try { return JSON.parse(t) } catch (_) { return dflt } },
  contentHash(text) { return __contentHash(text) },
  async runHelper(cmd, args) {
    var parts = [cmd].concat(args || []).map(function (a) { return __q(String(a)) }).join(' ')
    var out = await __sh(parts + ' 2>&1; echo __SR_EXIT:$?')
    var m = String(out || '').match(/__SR_EXIT:(\\d+)\\s*$/)
    var status = m ? Number(m[1]) : 1
    var stdout = m ? String(out).slice(0, m.index).replace(/\\n$/, '') : String(out || '')
    return { ok: status === 0, status: status, stdout: stdout, stderr: '' }
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
  return __require('showrunner.js').showrunner({ workItem: wi })
}
`

function emit() {
  const factories = MODULES.map((f) => '// ===== ' + f + ' =====\n' + factory(f, fs.readFileSync(path.join(LIB, f), 'utf8')))
  return PREAMBLE + '\n' + factories.join('\n') + '\n' + ENTRY
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
