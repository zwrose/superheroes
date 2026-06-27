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
// (b) Execute it in a sandbox that has NO require and NO Node builtins. `export const meta` is ESM
//     syntax, so strip the `export ` keyword for the CommonJS-style eval. Set __SR_RUN=false so the
//     auto-run entry is skipped and the registry is exposed for the compose assertion.
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
vm.runInContext('globalThis.__SR_RUN = false;\n' + text, sandbox, { timeout: 5000 })
const sr = sandbox.globalThis.__sr_require('showrunner.js')
assert.strictEqual(typeof sr.showrunner, 'function', 'bundle did not compose a showrunner export')
assert.ok(/const\s+meta\s*=/.test(text), 'bundle missing meta')
console.log('OK: bundle composes + executes in a no-require sandbox + exports showrunner')
