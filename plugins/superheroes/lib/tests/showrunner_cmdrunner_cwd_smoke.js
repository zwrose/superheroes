// plugins/superheroes/lib/tests/showrunner_cmdrunner_cwd_smoke.js
// TDD: FR-5 cwd-rooting for cmdRunner (and renderAndPostReadout).
//
// The bug: cmdRunner() embeds the raw `${cmd}` into its prompt without selfContained(), so
// when the courier leaf executes it the cwd is whatever the leaf landed in — not deterministic.
// The fix: wrap the command with selfContained() inside cmdRunner so every lib-leaf command
// carries an explicit `cd <root> && ` prefix when __SR_ROOT is set.
//
// Assertions:
//   (A1) cmdRunner with __SR_ROOT set: prompt embeds `cd '<root>' && <cmd>` (self-contained).
//   (A2) cmdRunner with __SR_ROOT UNSET: prompt embeds the raw <cmd> unchanged (no cd prefix).
//   (A3) cmdRunner with a cmd already starting with `cd `: stays single-cd (no double-prefix).
//   (B1) renderAndPostReadout with __SR_ROOT set: the loop_readout.py agent call is cd-prefixed.
//   (B2) renderAndPostReadout with __SR_ROOT UNSET: the loop_readout.py call is NOT cd-prefixed.

'use strict'
const assert = require('assert')

global.log = () => {}
global.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))

// ---------------------------------------------------------------------------
// (A) cmdRunner cwd-rooting
// ---------------------------------------------------------------------------
;(async () => {
  const ROOT = '/test-repo-root'
  const CMD = 'python3 plugins/superheroes/lib/some_cli.py --work-item wi'

  // (A1) __SR_ROOT set -> prompt contains `cd '<root>' && <cmd>`
  {
    delete require.cache[require.resolve('../showrunner.js')]
    const sr = require('../showrunner.js')
    const savedRoot = globalThis.__SR_ROOT
    globalThis.__SR_ROOT = ROOT
    const captured = []
    global.agent = async (p, opts) => { captured.push({ p, opts }); return { ok: true } }
    await sr.cmdRunner(CMD, { schema: { type: 'object', required: ['ok'] } })
    globalThis.__SR_ROOT = savedRoot
    assert.strictEqual(captured.length, 1, '(A1) cmdRunner makes exactly one agent call')
    const prompt = captured[0].p
    const expected = `cd '${ROOT}' && ${CMD}`
    assert.ok(prompt.includes(expected),
      `(A1) cmdRunner prompt must contain cd-rooted command when __SR_ROOT is set.\nExpected: ${expected}\nGot: ${prompt.slice(0, 300)}`)
    assert.ok(!prompt.match(new RegExp(`cd '${ROOT}' && cd '${ROOT}'`)),
      '(A1) no double-cd in the cmdRunner prompt')
  }

  // (A2) __SR_ROOT unset -> prompt contains raw command, no cd prefix
  {
    delete require.cache[require.resolve('../showrunner.js')]
    const sr = require('../showrunner.js')
    const savedRoot = globalThis.__SR_ROOT
    delete globalThis.__SR_ROOT
    const captured = []
    global.agent = async (p, opts) => { captured.push({ p, opts }); return { ok: true } }
    await sr.cmdRunner(CMD, { schema: { type: 'object', required: ['ok'] } })
    if (savedRoot !== undefined) globalThis.__SR_ROOT = savedRoot
    assert.strictEqual(captured.length, 1, '(A2) cmdRunner makes exactly one agent call')
    const prompt = captured[0].p
    assert.ok(prompt.includes(CMD),
      `(A2) cmdRunner prompt must contain the raw command when __SR_ROOT is unset.\nExpected substring: ${CMD}\nGot: ${prompt.slice(0, 300)}`)
    assert.ok(!prompt.includes('cd '),
      `(A2) cmdRunner prompt must NOT contain cd prefix when __SR_ROOT is unset.\nGot: ${prompt.slice(0, 300)}`)
  }

  // (A3) command already starting with `cd ` -> no double-prefix even when __SR_ROOT set
  {
    delete require.cache[require.resolve('../showrunner.js')]
    const sr = require('../showrunner.js')
    const savedRoot = globalThis.__SR_ROOT
    globalThis.__SR_ROOT = ROOT
    const CD_CMD = `cd /build-worktree && python3 plugins/superheroes/lib/review_code_config.py --root "$(git rev-parse --show-toplevel)"`
    const captured = []
    global.agent = async (p, opts) => { captured.push({ p, opts }); return { verifyCommand: 'none', tiers: {} } }
    await sr.cmdRunner(CD_CMD, { schema: { type: 'object' } })
    globalThis.__SR_ROOT = savedRoot
    assert.strictEqual(captured.length, 1, '(A3) cmdRunner makes exactly one agent call')
    const prompt = captured[0].p
    assert.ok(prompt.includes(CD_CMD),
      `(A3) cmdRunner must leave a cd-prefixed command unchanged (no double-prefix).\nExpected substring: ${CD_CMD}\nGot: ${prompt.slice(0, 300)}`)
    assert.ok(!prompt.includes(`cd '${ROOT}' && cd `),
      `(A3) no double-cd in prompt when command already starts with cd.\nGot: ${prompt.slice(0, 300)}`)
  }

  // ---------------------------------------------------------------------------
  // (B) renderAndPostReadout: loop_readout.py agent call must be cd-prefixed
  // ---------------------------------------------------------------------------
  // Note: renderAndPostReadout uses a direct agent() call (not cmdRunner) for loop_readout.py,
  // and a cmdRunner() call for readout_post.py. Both need selfContained when __SR_ROOT is set.
  // We stub io() writeFile to avoid real fs access.

  // renderAndPostReadout(workItem, runDir, verdict) makes a direct agent() call (label 'readout')
  // that runs loop_readout.py wrapped in selfContained(), then a cmdRunner() readout_post.py call.
  // We capture the 'readout'-labelled prompt and assert its cd-rooting. io().writeFile is stubbed to
  // avoid fs; the readout agent returns text; cmdRunner's readout_post call returns a posted shape.
  const READOUT_CMD = 'python3 plugins/superheroes/lib/loop_readout.py --record'
  function captureReadoutPrompt(rootValue) {
    delete require.cache[require.resolve('../showrunner.js')]
    const sr = require('../showrunner.js')
    const savedRoot = globalThis.__SR_ROOT
    if (rootValue === undefined) delete globalThis.__SR_ROOT
    else globalThis.__SR_ROOT = rootValue
    let readoutPrompt = null
    global.agent = async (p, opts) => {
      if ((opts && opts.label) === 'readout') { readoutPrompt = p; return 'readout text' }
      return { posted: true }
    }
    sr.__setIo && sr.__setIo({ writeFile: async () => {} })
    return sr.renderAndPostReadout('wi', '/tmp/run-dir', { verdict: 'changes-requested' })
      .then(() => { if (savedRoot === undefined) delete globalThis.__SR_ROOT; else globalThis.__SR_ROOT = savedRoot; return readoutPrompt })
  }

  // (B1) __SR_ROOT set -> the loop_readout.py 'readout' prompt is cd-prefixed
  {
    const prompt = await captureReadoutPrompt(ROOT)
    assert.ok(prompt && prompt.includes(READOUT_CMD), '(B1) renderAndPostReadout issues the loop_readout.py readout call')
    assert.ok(prompt.includes(`cd '${ROOT}' && ${READOUT_CMD}`),
      `(B1) loop_readout.py prompt must be cd-rooted when __SR_ROOT is set.\nExpected substring: cd '${ROOT}' && ${READOUT_CMD}\nGot: ${prompt.slice(0, 300)}`)
  }

  // (B2) __SR_ROOT unset -> the loop_readout.py 'readout' prompt is NOT cd-prefixed
  {
    const prompt = await captureReadoutPrompt(undefined)
    assert.ok(prompt && prompt.includes(READOUT_CMD), '(B2) renderAndPostReadout issues the loop_readout.py readout call')
    assert.ok(!prompt.includes('cd '),
      `(B2) loop_readout.py prompt must NOT contain a cd prefix when __SR_ROOT is unset.\nGot: ${prompt.slice(0, 300)}`)
  }

  console.log('OK: cmdRunner + renderAndPostReadout cwd-rooting (A1/A2/A3 cmdRunner, B1/B2 loop_readout)')
})().catch((e) => { console.error('FAIL:', e.message || e, e.stack || ''); process.exit(1) })
