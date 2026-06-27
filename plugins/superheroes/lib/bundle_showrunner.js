// plugins/superheroes/lib/bundle_showrunner.js
// Emit a self-contained Workflow-tool script. Strategy: a tiny module registry. Each real spine
// module is wrapped in a factory (its own scope), and a __require shim resolves inter-module
// requires; ./io_seam.js resolves to the preamble's leaf-bash io (no fs/path/os in the sandbox).
const fs = require('fs')
const path = require('path')

const LIB = __dirname
// io_seam is intentionally absent: the preamble provides a leaf-bash io for it.
const MODULES = ['review_panel_shell.js', 'test_pilot_phase.js', 'build_phase.js', 'showrunner.js']

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
// inlined spine (which reads globals) sees them.
globalThis.agent = agent
globalThis.parallel = parallel
globalThis.log = (typeof log === 'function') ? log : (() => {})
// Leaf-bash io: every filesystem touch runs in a command-runner leaf, so the script body needs no fs.
function __q(s) { return "'" + String(s).replace(/'/g, "'\\\\''") + "'" }
async function __sh(cmd) { return agent('Run exactly this command and return ONLY its stdout, unchanged:\\n\\n' + cmd, { label: 'io' }) }
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
