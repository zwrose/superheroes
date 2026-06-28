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
const MODULES = ['circuit_breaker.js', 'loop_state.js', 'loop_synthesis.js', 'panel_tally.js',
                 'ci_status.js', 'verify_gate.js',
                 'review_panel_shell.js', 'test_pilot_phase.js', 'build_progress.js', 'build_phase.js',
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
globalThis.io = {
  join: __join, tmpdir() { return '/tmp' },
  async mkdirp(d) { await __sh('mkdir -p ' + __q(d)) },
  async writeFile(p, s) { const b = (typeof s === 'string') ? s : JSON.stringify(s); await __sh('cat > ' + __q(p) + " <<'__SR_EOF__'\\n" + b + '\\n__SR_EOF__') },
  async readText(p) { return __sh('cat ' + __q(p) + ' 2>/dev/null || true') },
  async readJson(p, dflt) { const t = await __sh('cat ' + __q(p) + ' 2>/dev/null || true'); try { return JSON.parse(t) } catch (_) { return dflt } },
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
