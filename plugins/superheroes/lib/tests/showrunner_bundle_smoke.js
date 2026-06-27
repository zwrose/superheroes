// plugins/superheroes/lib/tests/showrunner_bundle_smoke.js
const assert = require('assert')
const fs = require('fs')
const path = require('path')
const vm = require('vm')
const bundlePath = path.join(__dirname, '..', 'showrunner.bundle.js')
let text = fs.readFileSync(bundlePath, 'utf8')

// (a) Static guard: no Node BUILTIN require survives (the registry shim's own require is fine).
for (const banned of [/require\(\s*['"](fs|path|os|child_process|crypto|vm)['"]\s*\)/]) {
  assert.ok(!banned.test(text), 'bundle leaks a Node builtin require: ' + banned)
}
// (a2) The Workflow runtime forbids these (they break resume) — they must never reach the bundle.
for (const banned of [/\bDate\.now\b/, /\bMath\.random\b/, /\bnew Date\b/]) {
  assert.ok(!banned.test(text), 'bundle uses a Workflow-forbidden API (breaks resume): ' + banned)
}
// (a3) `process` is absent in the runtime sandbox — every process.cwd()/process.env reference MUST be
//      typeof-guarded (procCwd/procEnv), or the live run crashes with "process is not defined".
for (const ln of text.split('\n')) {
  if (/process\.(cwd|env)\b/.test(ln)) {
    assert.ok(/typeof process !== 'undefined'/.test(ln),
      'bundle has an unguarded process reference (crashes the Workflow sandbox): ' + ln.trim())
  }
}
// (b) Execute it in a sandbox that has NO require and NO Node builtins. `export const meta` is ESM
//     syntax, so strip the `export ` keyword for the CommonJS-style eval. Set __SR_RUN=false so the
//     auto-run entry is skipped and the registry is exposed for the compose assertion.
//     The script is evaluated inside an async wrapper — faithful to how the Workflow runtime runs
//     it (an async context that awaits the body's top-level promise), which is ALSO what makes the
//     entry's top-level `return` parse (a bare top-level return in a plain vm script is a SyntaxError).
text = text.replace(/export\s+const\s+meta/, 'const meta')
const sandbox = { console, args: { workItem: 'x' } }
sandbox.globalThis = sandbox
sandbox.global = sandbox
sandbox.agent = async () => ({})
sandbox.parallel = async (thunks) => Promise.all((thunks || []).map((f) => f()))
sandbox.log = () => {}
vm.createContext(sandbox)
// A Node-builtin require inside any loaded module would throw here (no `require` in scope), and a
// duplicate const / orphaned export would be a SyntaxError at compile — both fail the smoke loudly.
// __SR_RUN=false skips the entry, so the async wrapper completes synchronously (no top-level await is
// reached) and the registry is set on globalThis by the time runInContext returns.
vm.runInContext('globalThis.__SR_RUN = false;\n;(async () => {\n' + text + '\n})();', sandbox, { timeout: 5000 })
const sr = sandbox.globalThis.__sr_require('showrunner.js')
assert.strictEqual(typeof sr.showrunner, 'function', 'bundle did not compose a showrunner export')
assert.ok(/const\s+meta\s*=/.test(text), 'bundle missing meta')
console.log('OK: bundle composes + executes in a no-require sandbox + exports showrunner')
