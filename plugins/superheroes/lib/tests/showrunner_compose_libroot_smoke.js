// plugins/superheroes/lib/tests/showrunner_compose_libroot_smoke.js
// #170 CI guard: the libRoot refactor must hold. Every `python3 <lib>/<cli>.py` compose now threads
// the spine CODE root through lib_root.libPath() (reading globalThis.__SR_LIB), so:
//   (A) NO raw `plugins/superheroes/lib` compose survives in the COMMITTED BUNDLE — the only allowed
//       occurrences are module header comments + the three sanctioned default fallbacks. A future
//       edit that hardcodes `python3 plugins/superheroes/lib/foo.py` instead of libPath() fails here.
//   (B) When __SR_LIB is set ABSOLUTE, a real compose (reconcile's recover_entry snapshot) resolves
//       under that absolute path and contains NO `plugins/superheroes/lib` literal.
//   (C) Fail-closed probe: an ABSOLUTE __SR_LIB whose dir is missing short-circuits reconcile to a
//       NAMED park ('spine code root missing (libRoot)'), not a raw python file-not-found.
'use strict'
const assert = require('assert')
const fs = require('fs')
const path = require('path')

const libRootMod = require('../lib_root.js')

// ── (A) static allowlist over the committed bundle ──────────────────────────────────────────────
{
  const bundle = fs.readFileSync(path.join(__dirname, '..', 'showrunner.bundle.js'), 'utf8')
  // The ONLY sanctioned appearances of the literal after the #170 refactor:
  const ALLOWED = [
    /^\s*\/\/ plugins\/superheroes\/lib\//,                          // module header comments
    /const DEFAULT_LIB = 'plugins\/superheroes\/lib'/,                // lib_root.js default
    /os\.path\.join\(os\.getcwd\(\), "plugins\/superheroes\/lib"\)/,  // pyLibDir() default python expr
    /globalThis\.__SR_LIB = .*'plugins\/superheroes\/lib'/,           // bundle ENTRY fallback
  ]
  const offenders = []
  bundle.split('\n').forEach((ln, i) => {
    if (ln.includes('plugins/superheroes/lib') && !ALLOWED.some((re) => re.test(ln))) {
      offenders.push((i + 1) + ': ' + ln.trim())
    }
  })
  assert.deepStrictEqual(offenders, [],
    'a raw `plugins/superheroes/lib` compose survived the #170 libRoot refactor — route it through ' +
    'lib_root.libPath()/pyLibDir()/pyLibScript():\n' + offenders.join('\n'))
}

// ── shared raw-module driver: capture reconcile's composed 'gather snapshot' command ────────────
global.log = () => {}
global.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))

function resetGlobals() {
  delete globalThis.__SR_ROOT
  delete globalThis.__SR_LIB
}

async function reconcileWith(libRootValue, snapshotStdout) {
  resetGlobals()
  globalThis.__SR_LIB = libRootValue
  delete require.cache[require.resolve('../showrunner.js')]
  const sr = require('../showrunner.js')
  let captured = null
  globalThis.agent = async (prompt) => { captured = String(prompt); return [{ index: 0, ok: true, stdout: snapshotStdout }] }
  const result = await sr.reconcile('wi-x')
  return { result, prompt: captured }
}

// persistPhase rides the runCourierJson path (not exec) — the courier returns a bare stdout string.
async function persistWith(libRootValue, courierStdout) {
  resetGlobals()
  globalThis.__SR_LIB = libRootValue
  delete require.cache[require.resolve('../showrunner.js')]
  const sr = require('../showrunner.js')
  let captured = null
  globalThis.agent = async (prompt, opts) => {
    if (opts && opts.label === 'save phase progress') captured = String(prompt)
    return courierStdout
  }
  const result = await sr.persistPhase('wi-x', { step: 1, phase: 'x', journalPayload: { phase: 'x' } })
  return { result, prompt: captured }
}

// The parseable failure object the probe echoes when an absolute code root is missing.
const MISSING_PAYLOAD = JSON.stringify({ ok: false, reason: libRootMod.MISSING_MARKER })

;(async () => {
  const ABS = '/opt/sr-libroot'   // absolute + free of the `plugins/superheroes/lib` substring

  // (B) absolute __SR_LIB -> the recover_entry compose points at the absolute path, no literal.
  {
    const snap = JSON.stringify({ checkpoint: null, world: {}, generation: 5, root: '/some/target/repo' })
    const { prompt } = await reconcileWith(ABS, snap)
    assert.ok(prompt, '(B) reconcile issued a gather-snapshot command')
    assert.ok(prompt.includes(ABS + '/recover_entry.py'),
      `(B) recover_entry compose must resolve under the absolute libRoot.\nGot: ${prompt.slice(0, 300)}`)
    assert.ok(!prompt.includes('plugins/superheroes/lib'),
      `(B) an absolute-libRoot compose must contain NO repo-relative literal.\nGot: ${prompt.slice(0, 300)}`)
    assert.ok(prompt.includes(`test -d '${ABS}'`),
      `(B) an absolute libRoot arms the fail-closed probe.\nGot: ${prompt.slice(0, 300)}`)
    // sanity: libPath itself resolves absolute
    globalThis.__SR_LIB = ABS
    assert.strictEqual(libRootMod.libPath('fence_cli.py'), ABS + '/fence_cli.py', '(B) libPath resolves absolute')
    resetGlobals()
  }

  // (C) missing absolute libRoot -> the leaf echoes the marker payload. BOTH probe sites — the
  //     launch-entry reconcile (exec) AND the once-per-phase persistPhase durable write (courier) —
  //     must fail closed to the SAME named park, so the back half is covered, not just startup.
  const MISS = '/opt/sr-missing-libroot'
  {
    // (C1) reconcile / startup entry.
    const { result, prompt } = await reconcileWith(MISS, MISSING_PAYLOAD)
    assert.ok(prompt.includes(`test -d '${MISS}'`), '(C1) probe present for a missing absolute root')
    assert.strictEqual(result.action, 'park_gate', '(C1) a missing spine code root fails closed to a park')
    assert.strictEqual(result.reason, 'spine code root missing (libRoot)',
      `(C1) the park must NAME the missing code root.\nGot: ${JSON.stringify(result)}`)
  }
  {
    // (C2) persistPhase / back-half once-per-phase durable write.
    const { result, prompt } = await persistWith(MISS, MISSING_PAYLOAD)
    assert.ok(prompt && prompt.includes(`test -d '${MISS}'`), '(C2) persistPhase save compose arms the probe')
    assert.ok(prompt.includes(MISS + '/phase_progress_entry.py'), '(C2) save compose resolves under the absolute libRoot')
    assert.ok(!prompt.includes('plugins/superheroes/lib'), '(C2) no repo-relative literal in the save compose')
    assert.strictEqual(result.ok, false, '(C2) a missing spine code root fails the durable write closed')
    assert.strictEqual(result.error, 'spine code root missing (libRoot)',
      `(C2) the back-half durable write must fail with the SAME named reason.\nGot: ${JSON.stringify(result)}`)
  }

  // (D) default (relative) libRoot -> byte-identical pre-#170 compose, probe emits nothing.
  {
    const snap = JSON.stringify({ checkpoint: null, world: {}, generation: 5, root: '/some/target/repo' })
    const { prompt } = await reconcileWith(undefined, snap)
    assert.ok(prompt.includes('python3 plugins/superheroes/lib/recover_entry.py'),
      `(D) default libRoot stays byte-identical.\nGot: ${prompt.slice(0, 300)}`)
    assert.ok(!prompt.includes('test -d '),
      `(D) dev/dogfood (relative) libRoot must NOT arm the probe.\nGot: ${prompt.slice(0, 300)}`)
  }

  resetGlobals()
  console.log('OK: #170 libRoot compose guard (A bundle-static, B absolute-resolve, C1/C2 fail-closed probe reconcile+persistPhase, D default byte-identical)')
})().catch((e) => { console.error('FAIL:', e.message || e, e.stack || ''); process.exit(1) })
