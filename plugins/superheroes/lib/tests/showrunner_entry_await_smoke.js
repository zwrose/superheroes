// plugins/superheroes/lib/tests/showrunner_entry_await_smoke.js
//
// Regression guard for the live-only entry-await bug (caught by the Tier-3 one-shot): the bundle's
// auto-run entry must `return` the showrunner() promise at the top level so the Workflow runtime —
// which runs the script in an async context and AWAITS the body's top-level promise — waits for the
// whole pipeline. The original entry fire-and-forgot the promise inside an un-awaited IIFE, so under
// the runtime the script tore down before any agent() ran (0 agents, instant exit). Bare `node`
// drained the microtask, which is why the offline smokes (all set __SR_RUN=false and call
// showrunner() directly) were blind to it.
//
// This guard FAITHFULLY emulates the runtime: it evaluates the bundle inside an async wrapper and
// CAPTURES the wrapper's promise, with a stub agent() that throws a sentinel on the first call
// (showrunner -> reconcile -> cmdRunner -> agent). If the entry returns/awaits the pipeline, that
// promise REJECTS with the sentinel. A fire-and-forget entry would resolve `undefined` instead — so
// this assertion fails loudly on regression.
const assert = require('assert')
const fs = require('fs')
const path = require('path')
const vm = require('vm')
const { markedStdout } = require('./_marked_stdout.js')

const SENTINEL = 'SR_ENTRY_AWAIT_SENTINEL'
const bundlePath = path.join(__dirname, '..', 'showrunner.bundle.js')
let text = fs.readFileSync(bundlePath, 'utf8').replace(/export\s+const\s+meta/, 'const meta')

// args is delivered as a JSON STRING by the Workflow runtime (observed live) — pass it that way so
// this guard also covers the entry's string-args parse: if parsing were dropped, wi would be null and
// the entry would throw "requires args.workItem" instead of surfacing the awaited pipeline's sentinel.
const sandbox = { console, args: JSON.stringify({ workItem: 'entry-await-probe' }), process: { env: {}, cwd: () => '/' } }
sandbox.globalThis = sandbox
sandbox.global = sandbox
// First leaf call after reconcile's gather snapshot throws the sentinel; its rejection must
// propagate out through the entry's returned promise iff the entry awaited/returned it.
sandbox.agent = async (prompt, opts) => {
  const label = (opts && opts.label) || ''
  if (label === 'gather snapshot' || String(prompt).includes('recover_entry.py')) {
    return markedStdout({
      checkpoint: null,
      world: { store_ok: true, current_content_hash: null, pr: null, seeded_empty: true },
      generation: 1,
      root: process.cwd(),
    })
  }
  if (label === 'read startup state') {
    return markedStdout({ ok: true, spec_gate: 'passed', model_overrides: {}, doc_dir: '', engine_prefs: {} })
  }
  if (opts && opts.courier) {
    if (String(prompt).includes('definition_doc.py read-gate')) {
      return JSON.stringify({ review: 'passed' })
    }
    if (String(prompt).includes('front_half_usable.py')) {
      return JSON.stringify({ usable: true, recorded: 'x', expected: 'x', missing_sections: [], placeholder: false })
    }
    return '{}'
  }
  throw new Error(SENTINEL)
}
sandbox.parallel = async (thunks) => Promise.all((thunks || []).map((f) => f()))
sandbox.log = () => {}
vm.createContext(sandbox)

// __SR_RUN left truthy so the entry runs. The async wrapper mirrors the runtime's async context and
// lets the entry's top-level `return` parse; runInContext yields the wrapper's promise as its value.
const runPromise = vm.runInContext('(async () => {\n' + text + '\n})();', sandbox, { timeout: 5000 })

assert.ok(runPromise && typeof runPromise.then === 'function',
  'entry did not yield a promise — the bundle script returned synchronously (fire-and-forget entry?)')

runPromise.then(
  (val) => {
    console.error('FAIL: entry resolved (' + JSON.stringify(val) + ') instead of awaiting the pipeline — '
      + 'the showrunner promise was fire-and-forgot, not returned at the top level.')
    process.exit(1)
  },
  (err) => {
    assert.ok(String(err && err.message).includes(SENTINEL),
      'entry rejected with an unexpected error (' + (err && err.message) + ') — expected the awaited '
      + 'pipeline to surface the stub agent sentinel')
    console.log('OK: bundle entry returns/awaits the showrunner pipeline (rejection propagated)')
  },
)
