// plugins/superheroes/lib/tests/showrunner_composed_exact_smoke.js
// #402 Part A: FR-8 composed-exact re-aligned to EXECUTED bytes. The spine registers the exact bytes a
// dumb-pipe leaf will run at the SINGLE dispatch chokepoint — courier_exec.recordComposedFromPrompt,
// called by the bundle preamble's agent wrapper with the FINAL prompt — so:
//   (1) the recorded command is byte-identical to what the leaf executes (extracted from the very prompt
//       that reaches the leaf), for BOTH dumb-pipe command leads, immune to any upstream rewrite;
//   (2) a smart-leaf free-form prompt (a builder/reviewer) is NEVER registered — the floor cannot widen
//       to commands the spine did not compose byte-for-byte;
//   (3) registration is fail-open (a throwing recorder never blocks/delays a dispatch) and re-entrant
//       (the recorder's own helper leaf, re-entering the chokepoint, does not recurse);
//   (4) through the REAL bundle preamble wrapper, a dumb-pipe dispatch records the executed bytes —
//       including a command already cd-wrapped by an outer rewrite (the byte-drift hazard #402 names).
// Run: node plugins/superheroes/lib/tests/showrunner_composed_exact_smoke.js
const assert = require('assert')
const fs = require('fs')
const path = require('path')
const vm = require('vm')
const courier = require('../courier_exec.js')

// ---------------------------------------------------------------------------
// (1)+(2)+(3): the pure chokepoint contract (module-level, no bundle).
// ---------------------------------------------------------------------------
function chokepointContract() {
  const seen = []
  courier.setComposedRecorder((cmd) => seen.push(cmd))
  try {
    // both dumb-pipe leads register a spine STATE-WRITE's exact bytes AFTER the first blank line, verbatim.
    // NOTE (#425): these 'Run exactly this …' fixtures are LEAD+BOUNDARY shape fixtures, deliberately
    // NOT byte-identical to promptFor's full output (the chokepoint keys only on the lead prefix and the
    // first blank line). Byte-fidelity of the REAL builders is owned by courier_dispatch_idiom_smoke.js,
    // which feeds recordComposedFromPrompt the actual promptFor/markedPromptFor prompts.
    courier.recordComposedFromPrompt(
      'Run exactly this command. Your entire reply must be the command\'s stdout, verbatim:\n\npython3 lib/build_state_cli.py record-reviewed --work-item wi')
    courier.recordComposedFromPrompt(
      // #425: the marked builder now states fidelity as transparency, not concealment-shaped prohibition;
      // the LEAD and the FIRST-blank-line boundary are byte-compatible, so the chokepoint is unaffected.
      'Execute this exact shell command via your command tool. ' + courier.FIDELITY_IS_TRANSPARENT_CLAUSE +
      '\n\npython3 lib/journal_entry.py --step x 2>&1; echo __SR_EXIT:$?')
    assert.deepStrictEqual(seen, [
      'python3 lib/build_state_cli.py record-reviewed --work-item wi',
      'python3 lib/journal_entry.py --step x 2>&1; echo __SR_EXIT:$?',
    ], 'records the exact executed bytes after the first blank line, for both dumb-pipe leads')

    // EVERY _SPINE_STATE_WRITE alternative gets a positive case (#402 review — test-001): dropping any
    // one of these allowlist arms must fail this test rather than silently reverting that state-write
    // class to the auto-mode classifier (the #395 endgame park). One command per remaining arm:
    seen.length = 0
    const perClass = {
      'prov_entry.py': 'python3 lib/prov_entry.py --step build --sha abc123',
      'fence_cli.py': 'python3 lib/fence_cli.py renew --lease L7',
      'ref_lock': 'python3 -c "import ref_lock; ref_lock.release(\'wi\')"',
      'base64.b64decode (__SR_W io writer)': 'python3 -c \'import os,sys,base64\nopen(sys.argv[1],"wb").write(base64.b64decode(sys.argv[2]))\' /store/x.json AA==',
    }
    for (const [cls, cmd] of Object.entries(perClass)) {
      courier.recordComposedFromPrompt('Run exactly this command. Your entire reply must be the command\'s stdout, verbatim:\n\n' + cmd)
    }
    assert.deepStrictEqual(seen, Object.values(perClass),
      'each remaining state-write class (prov, fence, ref_lock, base64 io-writer) registers its exact bytes')

    // a READ dumb pipe is NOT registered — reads are not blocked, and registering them would double cost.
    seen.length = 0
    courier.recordComposedFromPrompt('Run exactly this command. Your entire reply must be the command\'s stdout, verbatim:\n\ngit status')
    courier.recordComposedFromPrompt('Run exactly this command. Your entire reply must be the command\'s stdout, verbatim:\n\ngh pr view 12')
    assert.strictEqual(seen.length, 0, 'a READ dumb pipe registers nothing (scoped to state-write seams)')

    // a smart-leaf prompt (no dumb-pipe lead) is NEVER recorded — the floor cannot widen.
    courier.recordComposedFromPrompt('You are the builder. Implement task 7 by editing files and running tests.\n\ngit push origin main')
    courier.recordComposedFromPrompt('Review the diff for security issues.\n\nrm -rf /')
    assert.strictEqual(seen.length, 0, 'a smart-leaf free-form prompt registers nothing (no dumb-pipe lead)')

    // no command after the blank line -> nothing recorded.
    courier.recordComposedFromPrompt('Run exactly this command. Your entire reply must be the command\'s stdout, verbatim:\n\n')
    assert.strictEqual(seen.length, 0, 'an empty command registers nothing')
  } finally { courier.setComposedRecorder(null) }

  // no recorder wired -> a plain no-op, never a throw.
  assert.doesNotThrow(() => courier.recordComposedFromPrompt('Run exactly this command:\n\nls'),
    'no recorder wired -> no-op, never a throw')

  // fail-open: a throwing recorder must NOT propagate (a record error never blocks a dispatch).
  courier.setComposedRecorder(() => { throw new Error('boom') })
  try {
    assert.doesNotThrow(() => courier.recordComposedFromPrompt('Run exactly this command:\n\npython3 lib/journal_entry.py --step x'),
      'a throwing recorder is swallowed (fail-open, UFR-2)')
  } finally { courier.setComposedRecorder(null) }

  // re-entrancy guard: a recorder that itself re-enters the chokepoint records ONCE, never recurses.
  let calls = 0
  courier.setComposedRecorder((cmd) => {
    calls += 1
    // simulate the recorder's own helper leaf re-entering the same chokepoint with a write command.
    courier.recordComposedFromPrompt('Execute this exact shell command...:\n\npython3 lib/journal_entry.py --step y')
  })
  try {
    courier.recordComposedFromPrompt('Run exactly this command:\n\npython3 lib/build_state_cli.py record-built --work-item wi')
    assert.strictEqual(calls, 1, 're-entrancy guard: the recorder fires exactly once, no recursion')
  } finally { courier.setComposedRecorder(null) }
}

// ---------------------------------------------------------------------------
// (4): byte-exactness through the REAL bundle preamble agent wrapper.
// ---------------------------------------------------------------------------
function loadBundle() {
  const bundlePath = path.join(__dirname, '..', 'showrunner.bundle.js')
  let text = fs.readFileSync(bundlePath, 'utf8').replace(/export\s+const\s+meta/, 'const meta')
  const sandbox = { console, args: { workItem: 'x' } }
  sandbox.globalThis = sandbox
  // the preamble captures `const __realAgent = agent` AT EVAL — install the canned dispatcher first.
  let lastDispatched = null
  sandbox.agent = async (prompt) => { lastDispatched = prompt; return '' }
  sandbox.parallel = async (thunks) => Promise.all((thunks || []).map((f) => f()))
  sandbox.log = () => {}
  vm.createContext(sandbox)
  // __SR_RUN=false skips the auto-run entry; the run-identity global is the SEPARATE __SR_RUN_CTX.
  vm.runInContext('globalThis.__SR_RUN = false;\n;(async () => {\n' + text + '\n})();', sandbox, { timeout: 5000 })
  return { sandbox, getLastDispatched: () => lastDispatched }
}

async function byteExactThroughPreamble() {
  const { sandbox, getLastDispatched } = loadBundle()
  const bundledCourier = sandbox.globalThis.__sr_require('courier_exec')
  const recorded = []
  // #402 review (test-006): assert criterion 1's ordering — registration fires BEFORE the leaf dispatch,
  // so the enforcer can see the frozen hash. On the FIRST dispatch through this fresh bundle the canned
  // __realAgent has not run yet, so getLastDispatched() must still be null when the recorder fires.
  let firstReg = true
  bundledCourier.setComposedRecorder((cmd) => {
    if (firstReg) {
      assert.strictEqual(getLastDispatched(), null,
        'registration precedes dispatch: the recorder fires before __realAgent (criterion 1)')
      firstReg = false
    }
    recorded.push(cmd)
  })

  // A dumb-pipe state-write dispatch through the bundle's globalThis.agent (the single choke-point
  // wrapper) records the FINAL prompt's command verbatim — this is what the leaf executes.
  await sandbox.globalThis.agent(
    'Run exactly this command. Your entire reply must be the command\'s stdout, verbatim:\n\npython3 lib/journal_entry.py --step ship', { courier: true })
  assert.deepStrictEqual(recorded, ['python3 lib/journal_entry.py --step ship'],
    'the preamble wrapper records the dumb-pipe state-write command byte-exactly')

  // The byte-drift hazard #402 names: a command ALREADY cd-wrapped by an outer rewrite
  // (withTargetCommandPrompts) reaches the wrapper post-rewrite — so the recorded bytes still equal the
  // executed bytes, because we extract from the final prompt, never a pre-rewrite copy.
  recorded.length = 0
  await sandbox.globalThis.agent(
    "Run exactly this command. Your entire reply must be the command\'s stdout, verbatim:\n\ncd '/managed/wt' && python3 lib/prov_entry.py --step build", { courier: true })
  assert.deepStrictEqual(recorded, ["cd '/managed/wt' && python3 lib/prov_entry.py --step build"],
    'a cd-wrapped command records the FINAL (executed) bytes — no recorded-vs-dispatched drift')

  // A READ dumb pipe through the SAME wrapper records nothing (scoped to state-write seams).
  recorded.length = 0
  await sandbox.globalThis.agent('Run exactly this command. Your entire reply must be the command\'s stdout, verbatim:\n\ngit status', { courier: true })
  assert.strictEqual(recorded.length, 0, 'a READ dumb pipe through the wrapper registers nothing')

  // A smart leaf dispatched through the SAME wrapper records nothing.
  await sandbox.globalThis.agent('You are the builder. Implement task 7.\n\nedit files', {})
  assert.strictEqual(recorded.length, 0, 'a smart-leaf dispatch through the wrapper registers nothing')
}

async function main() {
  chokepointContract()
  await byteExactThroughPreamble()
  console.log('ok: composed-exact registers executed bytes at the single chokepoint, byte-exact + floor-safe (#402)')
}

main().catch((e) => { console.error('FAIL:', e.message, e.stack); process.exit(1) })
