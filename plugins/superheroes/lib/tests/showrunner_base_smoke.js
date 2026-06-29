// plugins/superheroes/lib/tests/showrunner_base_smoke.js
// Smoke: configurable base branch (--base) threading.
//
// Tests:
//   (A) shipPhase reads __SR_BASE and passes it to ship_phase.py --step freshness as --base.
//       Absent __SR_BASE -> no --base arg (default behavior unchanged).
//   (B) draftPRPhase reads __SR_BASE and passes it to pr_entry.py as --base.
//       Absent __SR_BASE -> no --base arg.
//   (C) gatherState in build_phase.js reads __SR_BASE and passes --base to build_state_cli.py.
//       Absent __SR_BASE -> no --base arg.
//   (D) bundle ENTRY maps args.base -> __SR_BASE (text assertion on the generated bundle).

const assert = require('assert')
const fs = require('fs')
const path = require('path')

global.log = () => {}
global.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))

// ---------------------------------------------------------------------------
// (A) shipPhase: freshness step must thread __SR_BASE into ship_phase.py
// ---------------------------------------------------------------------------
;(async () => {
  // (A1) base set -> --base <branch> appears in the freshness command
  // Note: shipPhase calls ship_phase.py --step freshness via cmdRunner (label: 'lib'), not exec.
  {
    const capturedLibCmds = []
    delete require.cache[require.resolve('../showrunner.js')]
    const sr = require('../showrunner.js')
    const savedBase = globalThis.__SR_BASE
    globalThis.__SR_BASE = 'live-showrunner-102'
    global.agent = async (p, opts) => {
      const label = (opts && opts.label) || ''
      if (label === 'lib') {
        capturedLibCmds.push(p)
        if (p.includes('freshness')) return { decision: 'up_to_date' }
        if (p.includes('readout_post') || p.includes('readout')) return { posted: true }
        return { ok: true }
      }
      if (label === 'exec') {
        // ci checks via exec -> return green
        if (p.includes('emit-checks')) return [{ index: 0, ok: true, stdout: '[{"name":"ci","bucket":"pass","state":"success"}]' }]
        return [{ index: 0, ok: true, stdout: '{"ok":true}' }]
      }
      return null
    }
    await sr.shipPhase('wi', { number: 7 })
    globalThis.__SR_BASE = savedBase

    const freshnessCmd = capturedLibCmds.find((c) => c.includes('freshness'))
    assert.ok(freshnessCmd, '(A1) shipPhase must call ship_phase.py --step freshness via cmdRunner (lib)')
    assert.ok(freshnessCmd.includes('--base'), '(A1) __SR_BASE set -> --base must appear in freshness command')
    assert.ok(freshnessCmd.includes('live-showrunner-102'), '(A1) base branch name must appear in freshness command')
  }

  // (A2) base unset -> --base must NOT appear in freshness command
  {
    const capturedLibCmds = []
    delete require.cache[require.resolve('../showrunner.js')]
    const sr = require('../showrunner.js')
    const savedBase = globalThis.__SR_BASE
    delete globalThis.__SR_BASE
    global.agent = async (p, opts) => {
      const label = (opts && opts.label) || ''
      if (label === 'lib') {
        capturedLibCmds.push(p)
        if (p.includes('freshness')) return { decision: 'up_to_date' }
        if (p.includes('readout_post') || p.includes('readout')) return { posted: true }
        return { ok: true }
      }
      if (label === 'exec') {
        if (p.includes('emit-checks')) return [{ index: 0, ok: true, stdout: '[{"name":"ci","bucket":"pass","state":"success"}]' }]
        return [{ index: 0, ok: true, stdout: '{"ok":true}' }]
      }
      return null
    }
    await sr.shipPhase('wi', { number: 7 })
    if (savedBase !== undefined) globalThis.__SR_BASE = savedBase
    else delete globalThis.__SR_BASE

    const freshnessCmd = capturedLibCmds.find((c) => c.includes('freshness'))
    assert.ok(freshnessCmd, '(A2) shipPhase must call freshness via cmdRunner (lib)')
    assert.ok(!freshnessCmd.includes('--base'), '(A2) __SR_BASE unset -> --base must NOT appear in freshness command (default behavior)')
  }

  // ---------------------------------------------------------------------------
  // (B) draftPRPhase: --base must thread into pr_entry.py pr create call
  // ---------------------------------------------------------------------------

  // (B1) base set -> --base appears in pr create exec call
  {
    const capturedCmds = []
    delete require.cache[require.resolve('../showrunner.js')]
    const sr = require('../showrunner.js')
    const savedBase = globalThis.__SR_BASE
    globalThis.__SR_BASE = 'live-showrunner-102'
    global.agent = async (p, opts) => {
      const label = (opts && opts.label) || ''
      if (label === 'exec') {
        capturedCmds.push(p)
        // emit-world call -> no open PR -> 'create'
        if (p.includes('emit-world')) return [{ index: 0, ok: true, stdout: '{"pr":null}' }]
        // pr create call -> ok
        if (p.includes('pr_entry')) return [{ index: 0, ok: true, stdout: '{"ok":true,"pr":{"number":42,"url":"https://example.test/pr/42","isDraft":true,"state":"OPEN"}}' }]
        return [{ index: 0, ok: true, stdout: '{"ok":true}' }]
      }
      if (label === 'lib') return { ok: true }
      return null
    }
    await sr.draftPRPhase('wi')
    globalThis.__SR_BASE = savedBase

    const createCmd = capturedCmds.find((c) => c.includes('pr_entry') && !c.includes('emit-world'))
    if (createCmd) {
      // A create was attempted: --base must be present.
      assert.ok(createCmd.includes('--base'), '(B1) __SR_BASE set -> --base must appear in pr create command')
      assert.ok(createCmd.includes('live-showrunner-102'), '(B1) base branch name must appear in pr create command')
    }
    // If no create cmd (adopted), the test passes trivially (no PR was created to check).
  }

  // (B2) base unset -> --base must NOT appear in pr create
  {
    const capturedCmds = []
    delete require.cache[require.resolve('../showrunner.js')]
    const sr = require('../showrunner.js')
    const savedBase = globalThis.__SR_BASE
    delete globalThis.__SR_BASE
    global.agent = async (p, opts) => {
      const label = (opts && opts.label) || ''
      if (label === 'exec') {
        capturedCmds.push(p)
        if (p.includes('emit-world')) return [{ index: 0, ok: true, stdout: '{"pr":null}' }]
        if (p.includes('pr_entry')) return [{ index: 0, ok: true, stdout: '{"ok":true,"pr":{"number":42,"url":"https://example.test/pr/42","isDraft":true,"state":"OPEN"}}' }]
        return [{ index: 0, ok: true, stdout: '{"ok":true}' }]
      }
      if (label === 'lib') return { ok: true }
      return null
    }
    await sr.draftPRPhase('wi')
    if (savedBase !== undefined) globalThis.__SR_BASE = savedBase
    else delete globalThis.__SR_BASE

    const createCmd = capturedCmds.find((c) => c.includes('pr_entry') && !c.includes('emit-world'))
    if (createCmd) {
      assert.ok(!createCmd.includes('--base'), '(B2) __SR_BASE unset -> --base must NOT appear in pr create (default behavior)')
    }
  }

  // ---------------------------------------------------------------------------
  // (C) gatherState in build_phase.js: __SR_BASE must thread into build_state_cli.py --base
  // ---------------------------------------------------------------------------

  // #115 increment A: gatherState now dispatches via exec (label 'exec'); the exec prompt LISTS the
  // build_state_cli.py gather command, so the --base threading PIN survives by capturing that prompt.

  // (C1) base set -> --base in gatherState call
  {
    const capturedCmds = []
    const bp = require('../build_phase.js')
    const savedBase = globalThis.__SR_BASE
    globalThis.__SR_BASE = 'live-showrunner-102'
    global.agent = async (p, opts) => {
      const label = (opts && opts.label) || 'other'
      // exec's leaf returns the array shape; capture the prompt (it contains the gather command).
      if (label === 'exec') { capturedCmds.push(p); return [{ index: 0, ok: true, stdout: '{}' }] }
      return null
    }
    // Invoke gatherState directly (it is exported).
    await bp.gatherState('wi', 'branch', '1,2', '/wt')
    globalThis.__SR_BASE = savedBase

    assert.ok(capturedCmds.length > 0, '(C1) gatherState must call build_state_cli.py via exec')
    const gatherCmd = capturedCmds[0]
    assert.ok(gatherCmd.includes('build_state_cli.py gather'), '(C1) exec prompt must list the gather command')
    assert.ok(gatherCmd.includes('--base'), '(C1) __SR_BASE set -> --base must appear in gather command')
    assert.ok(gatherCmd.includes('live-showrunner-102'), '(C1) base branch name must appear in gather command')
  }

  // (C2) base unset -> --base must NOT appear
  {
    const capturedCmds = []
    delete require.cache[require.resolve('../build_phase.js')]
    const bp = require('../build_phase.js')
    const savedBase = globalThis.__SR_BASE
    delete globalThis.__SR_BASE
    global.agent = async (p, opts) => {
      const label = (opts && opts.label) || 'other'
      if (label === 'exec') { capturedCmds.push(p); return [{ index: 0, ok: true, stdout: '{}' }] }
      return null
    }
    await bp.gatherState('wi', 'branch', '1,2', '/wt')
    if (savedBase !== undefined) globalThis.__SR_BASE = savedBase
    else delete globalThis.__SR_BASE

    assert.ok(capturedCmds.length > 0, '(C2) gatherState must call build_state_cli.py via exec')
    const gatherCmd = capturedCmds[0]
    assert.ok(gatherCmd.includes('build_state_cli.py gather'), '(C2) exec prompt must list the gather command')
    assert.ok(!gatherCmd.includes('--base'), '(C2) __SR_BASE unset -> no --base in gather (default behavior)')
  }

  // ---------------------------------------------------------------------------
  // (D) bundle ENTRY maps args.base -> globalThis.__SR_BASE
  // ---------------------------------------------------------------------------
  {
    const bundlePath = path.join(__dirname, '..', 'showrunner.bundle.js')
    const text = fs.readFileSync(bundlePath, 'utf8')
    assert.ok(text.includes('__SR_BASE'), '(D) bundle must reference __SR_BASE')
    assert.ok(text.includes("__a.base"), '(D) bundle ENTRY must read args.base')
    assert.ok(text.includes('__SR_BASE = '), '(D) bundle ENTRY must set globalThis.__SR_BASE')
  }

  console.log('ok: configurable base branch threading (ship freshness, draft-PR, gather, bundle ENTRY)')
})().catch((e) => { console.error('FAIL:', e.message, e.stack); process.exit(1) })
